#pragma once
#include <Adafruit_GC9A01A.h>
#include "battery.h"
#include "device_ui.h"
#include "motion.h"
namespace brelock {
class PsramCanvas16 : public GFXcanvas16 {
 public:
  PsramCanvas16();
  void initialize();
};
class DeviceDisplay {
 public:
  DeviceDisplay();
  void begin(const char *deviceId);
  void wake(uint32_t now);
  void pollTouch(uint32_t now, const HostStatus &host);
  DeviceAction takeAction() { return ui_.takeAction(); }
  uint8_t buttonEventCount() const { return 0; }
  bool buttonEventActive(uint32_t) const { return false; }
  void update(uint32_t now, const MotionSnapshot &motion,
              const BatterySnapshot &battery, bool bleHealthy, bool imuPresent,
              const HostStatus &host);
  bool touchPresent() const { return touchPresent_; }
  uint8_t touchChipId() const { return touchChipId_; }
  uint32_t touchReadErrors() const { return touchReadErrors_; }
 private:
  Adafruit_GC9A01A lcd_;
  PsramCanvas16 canvas_;
  uint16_t *front_ = nullptr;
  DeviceUi ui_;
  bool touchPresent_ = false;
  uint8_t touchChipId_ = 0;
  bool awake_ = true;
  bool suppressWakeTouch_ = false;
  bool frontValid_ = false;
  uint8_t touchFailures_ = 0;
  uint32_t lastWakeAt_ = 0, lastDrawAt_ = 0, lastTouchPollAt_ = 0;
  uint32_t touchReadErrors_ = 0;
  void flushChanges();
};
}  // namespace brelock
