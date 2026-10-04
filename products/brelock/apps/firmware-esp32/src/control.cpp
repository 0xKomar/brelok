#include "control.h"
namespace brelock {
bool decodeHostStatus(const uint8_t *bytes, std::size_t size, HostStatus &out) {
  if (size != 20 || (bytes[0] != 1 && bytes[0] != 2) || bytes[1] > 2 ||
      (bytes[2] & 0xF8) != 0 || bytes[3] > (bytes[0] == 1 ? 4 : 5) || bytes[4] > 4 ||
      bytes[5] > 100) return false;
  const uint8_t step = bytes[7] & 15, seconds = bytes[7] >> 4;
  if ((bytes[0] == 1 && bytes[7] != 0) ||
      (bytes[0] == 2 && (step == 0 || step > 3 || seconds > 2 ||
                       (bytes[3] != 5 && seconds != 0)))) return false;
  HostStatus value;
  value.protection = bytes[1];
  value.flags = bytes[2];
  value.calibration = bytes[3];
  value.feedback = bytes[4];
  value.calibrationPercent = bytes[5];
  value.calibrationStep = step;
  value.movementSeconds = seconds;
  value.rssiDbm = static_cast<int8_t>(bytes[6]);
  value.distanceCm = bytes[8] | (static_cast<uint16_t>(bytes[9]) << 8);
  value.acknowledgedSequence = bytes[10] | (static_cast<uint16_t>(bytes[11]) << 8);
  for (unsigned i = 0; i < 8; ++i)
    value.session |= static_cast<uint64_t>(bytes[12 + i]) << (i * 8);
  if (!value.session) return false;
  out = value;
  return true;
}
std::array<uint8_t, 12> encodeControl(DeviceAction action, uint16_t sequence,
                                     uint64_t session) {
  std::array<uint8_t, 12> bytes{};
  bytes[0] = 1;
  bytes[1] = static_cast<uint8_t>(action);
  bytes[2] = sequence & 0xFF;
  bytes[3] = sequence >> 8;
  for (unsigned i = 0; i < 8; ++i) bytes[4 + i] = session >> (i * 8);
  return bytes;
}
}  // namespace brelock
