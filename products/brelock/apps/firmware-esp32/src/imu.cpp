#include "imu.h"

#include <Arduino.h>

#include "bus_io.h"
#include "config.h"

namespace brelock {
namespace {

constexpr uint8_t kWhoAmI = 0x00;
constexpr uint8_t kCtrl1 = 0x02;
constexpr uint8_t kCtrl2 = 0x03;
constexpr uint8_t kCtrl3 = 0x04;
constexpr uint8_t kCtrl5 = 0x06;
constexpr uint8_t kCtrl7 = 0x08;
constexpr uint8_t kStatus0 = 0x2E;
constexpr uint8_t kTimestamp = 0x30;
constexpr uint8_t kAccel4g62Hz = 0x17;
constexpr uint8_t kGyro512dps62Hz = 0x57;

int16_t signedLittleEndian(const uint8_t *bytes) {
  return static_cast<int16_t>(static_cast<uint16_t>(bytes[0]) |
                              static_cast<uint16_t>(bytes[1]) << 8);
}

bool isClipped(int16_t value) {
  const int32_t wide = value;
  return wide >= 31128 || wide <= -31128;  // About 95% of full scale.
}

}  // namespace

bool ImuDriver::begin() {
  initialized_ = false;
  counterKnown_ = false;
  address_ = 0;
  for (uint8_t candidate : {static_cast<uint8_t>(0x6A), static_cast<uint8_t>(0x6B)}) {
    uint8_t identity[2]{};
    if (readRegisters(candidate, kWhoAmI, identity, sizeof(identity)) &&
        identity[0] == 0x05) {
      address_ = candidate;
      whoAmI_ = identity[0];
      revision_ = identity[1];
      break;
    }
  }
  if (!address_) {
    ++errors_;
    return false;
  }

  // Register values and scales verified against the Waveshare/QST example.
  // Disable first. CTRL1 enables address auto-increment and 4-wire SPI mode.
  // Hardware LPFs stay off: the motion processor applies its own 8 Hz filter.
  const uint8_t enable = config::kGyroEnabled ? 0x03 : 0x01;
  if (!writeRegister(address_, kCtrl7, 0) ||
      !writeRegister(address_, kCtrl1, 0x60) ||
      !writeRegister(address_, kCtrl2, kAccel4g62Hz) ||
      !writeRegister(address_, kCtrl3, kGyro512dps62Hz) ||
      !writeRegister(address_, kCtrl5, 0) ||
      !writeRegister(address_, kCtrl7, enable)) {
    ++errors_;
    return false;
  }
  uint8_t registers[7]{};
  if (!readRegisters(address_, kCtrl1, registers, sizeof(registers)) ||
      registers[1] != kAccel4g62Hz || registers[2] != kGyro512dps62Hz ||
      registers[6] != enable) {
    ++errors_;
    return false;
  }
  initialized_ = true;
  return true;
}

ImuReadResult ImuDriver::poll(ImuSample &out) {
  if (!initialized_) {
    return ImuReadResult::Error;
  }
  uint8_t status = 0;
  if (!readRegisters(address_, kStatus0, &status, 1)) {
    initialized_ = false;
    ++errors_;
    return ImuReadResult::Error;
  }
  if (!(status & 0x01)) {
    return ImuReadResult::NotReady;
  }
  // One auto-increment burst: 24-bit counter, temperature, ACC xyz, GYR xyz.
  uint8_t data[17]{};
  if (!readRegisters(address_, kTimestamp, data, sizeof(data))) {
    initialized_ = false;
    ++errors_;
    return ImuReadResult::Error;
  }
  const uint32_t counter = static_cast<uint32_t>(data[0]) |
                           static_cast<uint32_t>(data[1]) << 8 |
                           static_cast<uint32_t>(data[2]) << 16;
  if (counterKnown_ && counter == lastCounter_) {
    return ImuReadResult::NotReady;
  }
  counterKnown_ = true;
  lastCounter_ = counter;
  out = ImuSample{};
  out.atMs = millis();
  out.gyroValid = config::kGyroEnabled && (status & 0x02);
  for (unsigned i = 0; i < 3; ++i) {
    const int16_t acceleration = signedLittleEndian(data + 5 + 2 * i);
    const int16_t gyro = signedLittleEndian(data + 11 + 2 * i);
    out.accelerationG[i] = acceleration / 8192.0f;  // +/-4g -> 8192 LSB/g.
    out.gyroDps[i] = out.gyroValid ? gyro / 64.0f : 0.0f;
    out.clipped = out.clipped || isClipped(acceleration) ||
                  (out.gyroValid && isClipped(gyro));
  }
  return ImuReadResult::Sample;
}

}  // namespace brelock
