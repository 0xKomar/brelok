#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

#include "telemetry.h"

namespace brelock {

struct ImuSample {
  uint32_t atMs = 0;
  std::array<float, 3> accelerationG{};
  std::array<float, 3> gyroDps{};
  bool gyroValid = false;
  bool clipped = false;
};

struct MotionSnapshot {
  bool valid = false;
  bool gyroValid = false;
  bool moving = false;
  bool clipped = false;
  float accelerationRmsMg = 0.0f;
  float gyroRmsDps = 0.0f;
  uint16_t lastMotionAgeMs = kUnknownMotionAge;
  unsigned samplesInWindow = 0;
};

// No Arduino dependency: the same processor runs on the board and in host tests.
class MotionProcessor {
 public:
  void push(const ImuSample &sample);
  void invalidate();
  MotionSnapshot snapshot(uint32_t now) const;

 private:
  struct EnergySample {
    uint32_t atMs = 0;
    float acceleration = 0.0f;
    float gyro = 0.0f;
    bool gyroValid = false;
  };
  static constexpr std::size_t kCapacity = 96;
  std::array<EnergySample, kCapacity> window_{};
  std::size_t head_ = 0;
  std::size_t count_ = 0;
  std::array<float, 3> gravity_{};
  std::array<float, 3> dynamic_{};
  bool initialized_ = false;
  uint32_t lastSampleAt_ = 0;
  float accelerationSum_ = 0.0f;
  float gyroSum_ = 0.0f;
  unsigned gyroSamples_ = 0;
  bool moving_ = false;
  bool entering_ = false;
  bool exiting_ = false;
  uint32_t enterAt_ = 0;
  uint32_t exitAt_ = 0;
  bool motionSeen_ = false;
  uint32_t lastMotionAt_ = 0;
  bool clippingSeen_ = false;
  uint32_t lastClippingAt_ = 0;

  void removeOldest();
  bool windowReady() const;
  void updateMovement(uint32_t now);
};

}  // namespace brelock
