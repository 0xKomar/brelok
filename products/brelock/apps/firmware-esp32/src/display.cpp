#include "display.h"
#include <SPI.h>
#include <esp_heap_caps.h>
#include <cstdlib>
#include <cstring>
#include "board_pins.h"
#include "bus_io.h"
#include "config.h"
#include "ui_renderer.h"
namespace brelock {
namespace {
uint16_t *allocateFrame() {
  auto *memory = static_cast<uint16_t *>(heap_caps_malloc(
      240*240*sizeof(uint16_t),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  if (!memory) memory = static_cast<uint16_t *>(std::malloc(240*240*sizeof(uint16_t)));
  return memory;
}
}
PsramCanvas16::PsramCanvas16() : GFXcanvas16(240,240,false) {}
void PsramCanvas16::initialize() {
  if (!buffer) { buffer = allocateFrame(); buffer_owned = true; }
}
DeviceDisplay::DeviceDisplay()
    : lcd_(&SPI,board::kLcdDc,board::kLcdCs,board::kLcdReset) {}
void DeviceDisplay::begin(const char *) {
  pinMode(board::kBacklight,OUTPUT); digitalWrite(board::kBacklight,LOW);
  SPI.begin(board::kLcdSclk,board::kLcdMiso,board::kLcdMosi,board::kLcdCs);
  lcd_.begin(40000000); lcd_.setRotation(0); lcd_.fillScreen(0);
  canvas_.initialize(); front_ = allocateFrame();
  pinMode(board::kTouchReset,OUTPUT);
  digitalWrite(board::kTouchReset,HIGH); delay(50);
  digitalWrite(board::kTouchReset,LOW); delay(5);
  digitalWrite(board::kTouchReset,HIGH); delay(50);
  touchPresent_ = readRegisters(0x15,0xA7,&touchChipId_,1);
  if (touchPresent_) {
    // Continuous IRQs and no 2 s standby while awake: required for a 3 s hold.
    touchPresent_ = writeRegister(0x15,0xFA,0x70) &&
                    writeRegister(0x15,0xEC,0x04) &&
                    writeRegister(0x15,0xFE,1) &&
                    writeRegister(0x15,0xFB,0) &&
                    writeRegister(0x15,0xFC,0);
    pinMode(board::kTouchInterrupt,INPUT_PULLUP);
    // Avoid the ESP32-S3 IPC stack overflow while installing the GPIO ISR.
    // Read CST816S state at 50 Hz in the existing loop instead.
    // https://github.com/espressif/arduino-esp32/issues/10528
  }
  wake(millis());
}
void DeviceDisplay::wake(uint32_t now) {
  lastWakeAt_ = now; awake_ = true;
  if (touchPresent_) writeRegister(0x15,0xFE,1);
  digitalWrite(board::kBacklight,HIGH);
}
void DeviceDisplay::pollTouch(uint32_t now,const HostStatus &host) {
  if (!touchPresent_ || now-lastTouchPollAt_ < 20) return;
  lastTouchPollAt_ = now;
  uint8_t input[6]{};
  if (!readRegisters(0x15,0x01,input,sizeof(input))) {
    ++touchReadErrors_;
    if (++touchFailures_ >= 3) ui_.cancelTouch();
    return;
  }
  touchFailures_ = 0;
  const bool down = (input[1]&15) != 0 && (input[2]>>6) != 1;
  const int16_t x = ((input[2]&15)<<8)|input[3];
  const int16_t y = ((input[4]&15)<<8)|input[5];
  if (down) {
    if (!awake_) { wake(now); suppressWakeTouch_ = true; }
    lastWakeAt_ = now;
  }
  if (suppressWakeTouch_) {
    ui_.cancelTouch();
    if (!down) suppressWakeTouch_ = false;
    return;
  }
  // A hold advances only after a successful read of the contact state.
  // An I2C failure cannot cause the timer alone to dispatch a remote lock.
  ui_.touch(now,down,x,y,input[0],host);
}
void DeviceDisplay::flushChanges() {
  const auto *next = canvas_.getBuffer();
  uint16_t transfer[240*8];
  for (int y = 0; y < 240; y += 8) {
    int left = 240,right = -1;
    for (int row = 0; row < 8; ++row)
      for (int x = 0; x < 240; ++x)
        if (!frontValid_ || next[(y+row)*240+x] != front_[(y+row)*240+x]) {
          if (x < left) left = x;
          if (x > right) right = x;
        }
    if (right < left) continue;
    const int width = right-left+1;
    for (int row = 0; row < 8; ++row)
      std::memcpy(transfer+row*width,next+(y+row)*240+left,width*sizeof(uint16_t));
    lcd_.drawRGBBitmap(left,y,transfer,width,8);
    for (int row = 0; row < 8; ++row)
      std::memcpy(front_+(y+row)*240+left,next+(y+row)*240+left,width*sizeof(uint16_t));
  }
  frontValid_ = true;
}
void DeviceDisplay::update(uint32_t now,const MotionSnapshot &motion,
                           const BatterySnapshot &battery,bool bleHealthy,
                           bool,const HostStatus &host) {
  // Host navigation may wake the screen, but only a successful touch read may
  // advance the hold timer and dispatch an action.
  if (ui_.syncHost(now,host)) wake(now);
  if (awake_ && !ui_.touching() && config::kDisplayIdleMs > 0 &&
      now-lastWakeAt_ >= config::kDisplayIdleMs) {
    awake_ = false; digitalWrite(board::kBacklight,LOW);
    if (touchPresent_) writeRegister(0x15,0xFE,0);
  }
  const uint32_t refreshMs = ui_.holdPercent(now) > 0 ? 50 : 250;
  if (!awake_ || !canvas_.getBuffer() || !front_ || now-lastDrawAt_ < refreshMs) return;
  lastDrawAt_ = now;
  UiRenderState s;
  s.page = ui_.page(); s.host = host; s.online = host.fresh(now);
  s.bleHealthy = bleHealthy; s.touchReady = touchPresent_;
  s.moving = motion.valid && motion.moving; s.imuValid = motion.valid;
  s.batteryMv = battery.valid ? battery.millivolts : 0;
  s.holdPercent = ui_.holdPercent(now);
  renderDeviceUi(canvas_,s); flushChanges();
}
}  // namespace brelock
