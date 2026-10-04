#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace brelock {
constexpr char kTelemetryUuid[] = "9e20a101-6f7f-4d8a-9c21-4b52454c4f43";
constexpr char kHostStatusUuid[] = "9e20a102-6f7f-4d8a-9c21-4b52454c4f43";
constexpr char kCommandUuid[] = "9e20a103-6f7f-4d8a-9c21-4b52454c4f43";
constexpr uint32_t kHostStatusTimeoutMs = 2500;
enum class DeviceAction : uint8_t {
  None = 0, StartCalibration = 1, SaveCalibration = 2,
  LockNow = 3, CancelCalibration = 4
};
struct HostStatus {
  uint8_t protection = 0;
  uint8_t flags = 0;
  uint8_t calibration = 0;
  uint8_t feedback = 0;
  uint8_t calibrationPercent = 0;
  uint8_t calibrationStep = 0;
  uint8_t movementSeconds = 0;
  int8_t rssiDbm = -128;
  uint16_t distanceCm = 0xFFFF;
  uint16_t acknowledgedSequence = 0;
  uint64_t session = 0;
  uint32_t receivedAtMs = 0;
  bool fresh(uint32_t now) const {
    return session != 0 && now - receivedAtMs <= kHostStatusTimeoutMs;
  }
  bool lockAvailable() const { return (flags & 2) != 0; }
};
bool decodeHostStatus(const uint8_t *bytes, std::size_t size, HostStatus &out);
std::array<uint8_t, 12> encodeControl(DeviceAction action, uint16_t sequence,
                                     uint64_t session);
}  // namespace brelock
