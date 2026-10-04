#pragma once

#include <array>
#include <cstdint>

namespace brelock {

constexpr uint8_t kProtocolVersion = 3;
constexpr uint8_t kPreviousProtocolVersion = 2;
constexpr uint8_t kDeviceTypeKeyfob = 1;
constexpr uint16_t kUnknownMotionAge = 0xFFFF;
constexpr char kServiceUuid[] = "9e20a100-6f7f-4d8a-9c21-4b52454c4f43";

enum TelemetryFlag : uint8_t {
  kMotion = 1 << 0,
  kImuValid = 1 << 1,
  kGyroValid = 1 << 2,
  kClipped = 1 << 3,
  kBatteryValid = 1 << 4,
  // v3: latched briefly after a touch so the laptop can mark a setup point.
  kButtonEvent = 1 << 5,
};

struct Telemetry {
  std::array<uint8_t, 6> deviceId{};
  uint16_t bootId = 0;
  uint32_t sequence = 0;
  bool moving = false;
  bool imuValid = false;
  bool gyroValid = false;
  bool clipped = false;
  bool batteryValid = false;
  bool buttonEventActive = false;
  uint8_t buttonEventCount = 0;
  uint16_t accelerationRmsMg = 0;
  uint16_t gyroRmsDeciDps = 0;
  uint16_t lastMotionAgeMs = kUnknownMotionAge;
  uint16_t batteryMv = 0;
  int8_t nominalTxDbm = 3;
};

using TelemetryPayload = std::array<uint8_t, 24>;
using PrimaryAdvertisement = std::array<uint8_t, 31>;
using ScanResponse = std::array<uint8_t, 27>;

uint16_t quantizeU16(float value);
TelemetryPayload encodeTelemetry(const Telemetry &telemetry);
PrimaryAdvertisement createPrimaryAdvertisement(const Telemetry &telemetry);
ScanResponse createScanResponse();

}  // namespace brelock
