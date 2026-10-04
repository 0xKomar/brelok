#include "telemetry.h"

#include <algorithm>
#include <cmath>

namespace brelock {
namespace {

void writeU16(uint8_t *out, uint16_t value) {
  out[0] = static_cast<uint8_t>(value);
  out[1] = static_cast<uint8_t>(value >> 8);
}

void writeU32(uint8_t *out, uint32_t value) {
  for (unsigned i = 0; i < 4; ++i) {
    out[i] = static_cast<uint8_t>(value >> (8 * i));
  }
}

}  // namespace

uint16_t quantizeU16(float value) {
  if (!std::isfinite(value) || value <= 0.0f) {
    return 0;
  }
  return static_cast<uint16_t>(std::round(std::min(value, 65535.0f)));
}

TelemetryPayload encodeTelemetry(const Telemetry &t) {
  TelemetryPayload out{};
  out[0] = kProtocolVersion;
  out[1] = kDeviceTypeKeyfob;
  std::copy(t.deviceId.begin(), t.deviceId.end(), out.begin() + 2);
  writeU16(out.data() + 8, t.bootId);
  writeU32(out.data() + 10, t.sequence);
  // Invalid IMU data must never look like a current positive movement signal.
  const bool imuValid = t.imuValid && !t.clipped;
  const bool gyroValid = imuValid && t.gyroValid;
  out[14] = (imuValid && t.moving ? kMotion : 0) |
            (imuValid ? kImuValid : 0) |
            (gyroValid ? kGyroValid : 0) |
            (t.clipped ? kClipped : 0) |
            (t.batteryValid ? kBatteryValid : 0) |
            (t.buttonEventActive ? kButtonEvent : 0);
  writeU16(out.data() + 15, imuValid ? t.accelerationRmsMg : 0);
  writeU16(out.data() + 17, gyroValid ? t.gyroRmsDeciDps : 0);
  writeU16(out.data() + 19,
           imuValid ? t.lastMotionAgeMs : kUnknownMotionAge);
  writeU16(out.data() + 21, t.batteryValid ? t.batteryMv : 0);
  // v3 reuses the old nominal-TX byte for the wrapping touch event counter.
  // The nominal transmit power is a board constant and is not needed by the
  // receiver because it calibrates directly from observed RSSI.
  out[23] = t.buttonEventCount;
  return out;
}

PrimaryAdvertisement createPrimaryAdvertisement(const Telemetry &telemetry) {
  // Flags (3) + AD header (2) + test company ID (2) + telemetry (24) = 31.
  PrimaryAdvertisement out{};
  out[0] = 2;
  out[1] = 0x01;
  out[2] = 0x06;
  out[3] = 27;
  out[4] = 0xFF;
  out[5] = 0xFF;
  out[6] = 0xFF;
  const TelemetryPayload payload = encodeTelemetry(telemetry);
  std::copy(payload.begin(), payload.end(), out.begin() + 7);
  return out;
}

ScanResponse createScanResponse() {
  // Bluetooth UUIDs are serialized least-significant byte first.
  return {{0x11, 0x07,
           0x43, 0x4F, 0x4C, 0x45, 0x52, 0x4B, 0x21, 0x9C,
           0x8A, 0x4D, 0x7F, 0x6F, 0x00, 0xA1, 0x20, 0x9E,
           0x08, 0x09, 'b', 'r', 'e', 'L', 'o', 'c', 'k'}};
}

}  // namespace brelock
