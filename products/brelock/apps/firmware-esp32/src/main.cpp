#include <Arduino.h>
#include <Wire.h>
#include <esp_system.h>

#include <cstdio>

#include "battery.h"
#include "ble_beacon.h"
#include "board_pins.h"
#include "config.h"
#include "display.h"
#include "imu.h"
#include "motion.h"
#include "telemetry.h"

namespace {

brelock::ImuDriver imu;
brelock::MotionProcessor motion;
brelock::BatteryMonitor battery;
brelock::BleBeacon beacon;
brelock::DeviceDisplay display;
brelock::Telemetry telemetry;
char deviceId[13]{};
uint32_t lastImuPollAtUs = 0;
uint32_t lastImuRetryAt = 0;
uint32_t lastImuSampleAt = 0;
uint32_t lastTelemetryAt = 0;
uint32_t lastBatteryAt = 0;
uint32_t lastStatusAt = 0;
uint32_t receivedSamples = 0;
uint32_t previousSamples = 0;
uint32_t droppedUsbLines = 0;
float measuredSensorHz = 0.0f;
bool rawRecording = false;

bool writeUsbLine(const char *line, int length) {
  if (length > 0 && Serial.availableForWrite() >= length) {
    Serial.write(reinterpret_cast<const uint8_t *>(line), static_cast<size_t>(length));
    return true;
  }
  ++droppedUsbLines;
  return false;
}

void logImuInitialization(bool success) {
#if BRELOCK_DEBUG
  Serial.printf("[IMU] ready=%u address=0x%02X who=0x%02X revision=0x%02X "
                "acc=4g gyro=512dps odr=62.5Hz\n",
                success, imu.address(), imu.whoAmI(), imu.revision());
#endif
}

void updateTelemetry(uint32_t now) {
  const auto activity = motion.snapshot(now);
  const auto voltage = battery.snapshot();
  ++telemetry.sequence;
  telemetry.moving = activity.moving;
  telemetry.imuValid = activity.valid;
  telemetry.gyroValid = activity.gyroValid;
  telemetry.clipped = activity.clipped;
  telemetry.accelerationRmsMg = brelock::quantizeU16(activity.accelerationRmsMg);
  telemetry.gyroRmsDeciDps = brelock::quantizeU16(activity.gyroRmsDps * 10.0f);
  telemetry.lastMotionAgeMs = activity.lastMotionAgeMs;
  telemetry.batteryValid = voltage.valid;
  telemetry.batteryMv = voltage.millivolts;
  telemetry.buttonEventActive = display.buttonEventActive(now);
  telemetry.buttonEventCount = display.buttonEventCount();
  beacon.publish(telemetry);
}

void logRawSample(const brelock::ImuSample &sample) {
  if (!rawRecording) {
    return;
  }
  char line[192]{};
  const int length = std::snprintf(line, sizeof(line),
      "raw,%lu,%lu,%.5f,%.5f,%.5f,%.3f,%.3f,%.3f,%u,%u\n",
      static_cast<unsigned long>(sample.atMs),
      static_cast<unsigned long>(imu.sampleCounter()),
      sample.accelerationG[0], sample.accelerationG[1], sample.accelerationG[2],
      sample.gyroDps[0], sample.gyroDps[1], sample.gyroDps[2],
      sample.gyroValid, sample.clipped);
  if (length < static_cast<int>(sizeof(line))) {
    writeUsbLine(line, length);
  }
}

void logStatus(uint32_t now, float measuredHz) {
  const auto payload = brelock::encodeTelemetry(telemetry);
  const auto activity = motion.snapshot(now);
  char hex[49]{};
  for (unsigned i = 0; i < payload.size(); ++i) {
    std::snprintf(hex + 2 * i, 3, "%02X", payload[i]);
  }
  const auto &host = beacon.hostStatus();
  char line[1024]{};
  const int length = std::snprintf(line, sizeof(line),
      "{\"type\":\"status\",\"firmware\":\"%s\",\"device_id\":\"%s\","
      "\"uptime_ms\":%lu,\"boot_id\":%u,\"sequence\":%lu,\"published_sequence\":%lu,"
      "\"ble_ok\":%s,\"ble_errors\":%lu,\"ble_error\":%d,\"imu_errors\":%lu,"
      "\"imu_hz\":%.2f,\"flags\":%u,\"motion_valid\":%s,\"motion_samples\":%u,"
      "\"touch_ready\":%s,\"touch_errors\":%lu,"
      "\"gatt_connected\":%s,\"host_fresh\":%s,\"host_protection\":%u,"
      "\"host_distance_cm\":%u,\"host_rssi_dbm\":%d,\"host_calibration\":%u,"
      "\"host_calibration_step\":%u,\"host_movement_seconds\":%u,"
      "\"host_feedback\":%u,\"host_ack\":%u,"
      "\"acc_rms_mg\":%u,\"gyro_rms_deci_dps\":%u,"
      "\"motion_age_ms\":%u,\"battery_mv\":%u,\"payload_hex\":\"%s\","
      "\"usb_dropped\":%lu,\"heap_bytes\":%lu}\n",
      brelock::config::kFirmwareVersion, deviceId, static_cast<unsigned long>(now),
      telemetry.bootId, static_cast<unsigned long>(telemetry.sequence),
      static_cast<unsigned long>(beacon.publishedSequence()),
      beacon.healthy(now) ? "true" : "false", static_cast<unsigned long>(beacon.errors()),
      beacon.lastError(), static_cast<unsigned long>(imu.errors()), measuredHz, payload[14],
      activity.valid ? "true" : "false", activity.samplesInWindow,
      display.touchPresent() ? "true" : "false",
      static_cast<unsigned long>(display.touchReadErrors()),
      beacon.connected() ? "true" : "false", host.fresh(now) ? "true" : "false",
      host.protection, host.distanceCm, host.rssiDbm, host.calibration,
      host.calibrationStep, host.movementSeconds, host.feedback, host.acknowledgedSequence,
      telemetry.accelerationRmsMg, telemetry.gyroRmsDeciDps, telemetry.lastMotionAgeMs,
      telemetry.batteryMv, hex, static_cast<unsigned long>(droppedUsbLines),
      static_cast<unsigned long>(ESP.getFreeHeap()));
  if (length < static_cast<int>(sizeof(line))) {
    writeUsbLine(line, length);
  }
}

void serviceCommands(uint32_t now) {
  for (unsigned i = 0; i < 16 && Serial.available(); ++i) {
    switch (Serial.read()) {
      case 'r':
        rawRecording = !rawRecording;
        Serial.printf("# raw_csv=%s; columns=type,ms,sensor_counter,ax_g,ay_g,az_g,"
                      "gx_dps,gy_dps,gz_dps,gyro_valid,clipped\n",
                      rawRecording ? "on" : "off");
        break;
      case 'w':
        display.wake(now);
        break;
      case 's':
        logStatus(now, measuredSensorHz);
        break;
      default:
        break;
    }
  }
}

}  // namespace

void setup() {
  // Board USB-C uses CH343P -> UART0 (GPIO43/44), not native USB CDC.
  Serial.setTxBufferSize(1024);
  Serial.begin(115200);

  const uint64_t chipId = ESP.getEfuseMac() & 0xFFFFFFFFFFFFULL;
  std::snprintf(deviceId, sizeof(deviceId), "%012llX", chipId);
  for (unsigned i = 0; i < telemetry.deviceId.size(); ++i) {
    telemetry.deviceId[i] = static_cast<uint8_t>(chipId >> (8 * (5 - i)));
  }
  telemetry.bootId = static_cast<uint16_t>(esp_random());

  Wire.begin(brelock::board::kSda, brelock::board::kScl,
             brelock::config::kI2cClockHz);
  Wire.setTimeOut(brelock::config::kI2cTimeoutMs);
  display.begin(deviceId);
  battery.begin();
  const auto voltage = battery.snapshot();
  telemetry.batteryValid = voltage.valid;
  telemetry.batteryMv = voltage.millivolts;
  logImuInitialization(imu.begin());
  const bool bleStarted = beacon.begin(telemetry);

  const uint32_t now = millis();
  lastImuRetryAt = now;
  lastImuSampleAt = now;
  lastTelemetryAt = now;
  lastBatteryAt = now;
  lastStatusAt = now;
  lastImuPollAtUs = micros();
#if BRELOCK_DEBUG
  Serial.printf("[BOOT] breLock=%s board=Waveshare-S3-Touch id=%s boot=%u "
                "flash=%lu psram=%lu ble_init=%u\n",
                brelock::config::kFirmwareVersion, deviceId, telemetry.bootId,
                static_cast<unsigned long>(ESP.getFlashChipSize()),
                static_cast<unsigned long>(ESP.getPsramSize()), bleStarted);
  Serial.printf("[BLE] v3 telemetry + GATT control; primary=31B scan_response=27B interval=100ms tx=+3dBm "
                "service=%s; USB: r=raw CSV, s=status, w=wake\n", brelock::kServiceUuid);
  Serial.printf("[LCD] dc=%d cs=%d rst=%d sclk=%d mosi=%d bl=%d "
                "touch_ready=%u touch_id=0x%02X auto_sleep_ms=%u\n",
                brelock::board::kLcdDc, brelock::board::kLcdCs,
                brelock::board::kLcdReset, brelock::board::kLcdSclk,
                brelock::board::kLcdMosi, brelock::board::kBacklight,
                static_cast<unsigned>(display.touchPresent()),
                static_cast<unsigned>(display.touchChipId()),
                brelock::config::kDisplayIdleMs);
#else
  (void)bleStarted;
#endif
}

void loop() {
  using namespace brelock;
  uint32_t now = millis();
  beacon.poll(now);
  display.pollTouch(now, beacon.hostStatus());
  const auto action = display.takeAction();
  if (action != DeviceAction::None) beacon.sendAction(action, now);
  serviceCommands(now);

  const uint32_t nowUs = micros();
  if (imu.initialized() && nowUs - lastImuPollAtUs >= config::kImuPollUs) {
    lastImuPollAtUs = nowUs;
    ImuSample sample;
    const ImuReadResult result = imu.poll(sample);
    if (result == ImuReadResult::Sample) {
      lastImuSampleAt = sample.atMs;
      ++receivedSamples;
      motion.push(sample);
      logRawSample(sample);
    } else if (result == ImuReadResult::Error) {
      motion.invalidate();
      lastImuRetryAt = now;
    }
  }
  // I2C can cross a millisecond boundary. Never compare a new sample timestamp
  // against the older loop timestamp with unsigned subtraction.
  now = millis();
  if ((!imu.initialized() || now - lastImuSampleAt > config::kImuStaleMs) &&
      now - lastImuRetryAt >= config::kImuRetryMs) {
    lastImuRetryAt = now;
    motion.invalidate();
    logImuInitialization(imu.begin());
    lastImuSampleAt = millis();
  }
  now = millis();
  if (now - lastBatteryAt >= config::kBatteryMs) {
    lastBatteryAt = now;
    battery.update();
  }
  now = millis();
  if (now - lastTelemetryAt >= config::kTelemetryMs) {
    lastTelemetryAt = now;
    updateTelemetry(now);
  }
  if (now - lastStatusAt >= config::kStatusMs) {
    measuredSensorHz = (receivedSamples - previousSamples) * 1000.0f /
                       static_cast<float>(now - lastStatusAt);
    previousSamples = receivedSamples;
    lastStatusAt = now;
#if BRELOCK_DEBUG
    logStatus(now, measuredSensorHz);
#endif
  }
  display.update(now, motion.snapshot(now), battery.snapshot(), beacon.healthy(now),
                  imu.initialized(), beacon.hostStatus());
  delay(1);
}
