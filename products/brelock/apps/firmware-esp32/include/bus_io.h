#pragma once

#include <Wire.h>
#include <cstddef>
#include <cstdint>

namespace brelock {

// Wire's timeout is configured once in setup. Neither driver retries in a loop.
inline bool readRegisters(uint8_t address, uint8_t reg, uint8_t *out,
                          std::size_t length) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  const std::size_t received = Wire.requestFrom(
      address, static_cast<uint8_t>(length), static_cast<uint8_t>(true));
  if (received != length) {
    while (Wire.available()) {
      Wire.read();
    }
    return false;
  }
  for (std::size_t i = 0; i < length; ++i) {
    out[i] = static_cast<uint8_t>(Wire.read());
  }
  return true;
}

inline bool writeRegister(uint8_t address, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission(true) == 0;
}

}  // namespace brelock
