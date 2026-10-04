#include "motion.h"

#include <algorithm>
#include <cmath>

#include "config.h"

namespace brelock {

void MotionProcessor::invalidate() {
  head_ = 0;
  count_ = 0;
  initialized_ = false;
  accelerationSum_ = 0.0f;
  gyroSum_ = 0.0f;
  gyroSamples_ = 0;
  moving_ = false;
  entering_ = false;
  exiting_ = false;
  motionSeen_ = false;
}

void MotionProcessor::removeOldest() {
  const EnergySample &oldest = window_[head_];
  accelerationSum_ -= oldest.acceleration;
  gyroSum_ -= oldest.gyro;
  if (oldest.gyroValid) {
    --gyroSamples_;
  }
  head_ = (head_ + 1) % kCapacity;
  --count_;
}

bool MotionProcessor::windowReady() const {
  return count_ >= config::kMotionMinSamples &&
         lastSampleAt_ - window_[head_].atMs >= config::kMotionMinSpanMs;
}

void MotionProcessor::push(const ImuSample &sample) {
  for (unsigned i = 0; i < 3; ++i) {
    if (!std::isfinite(sample.accelerationG[i]) ||
        (sample.gyroValid && !std::isfinite(sample.gyroDps[i]))) {
      invalidate();
      return;
    }
  }
  if (sample.clipped) {
    invalidate();
    clippingSeen_ = true;
    lastClippingAt_ = sample.atMs;
    return;
  }
  uint32_t dtMs = initialized_ ? sample.atMs - lastSampleAt_ : 0;
  if (initialized_ && dtMs == 0) {
    return;  // A repeated sample is not another independent observation.
  }
  if (initialized_ && dtMs > config::kImuStaleMs) {
    invalidate();
    dtMs = 0;
  }
  if (!initialized_) {
    gravity_ = sample.accelerationG;
    dynamic_.fill(0.0f);
    initialized_ = true;
  }

  const float dtSeconds = dtMs / 1000.0f;
  const float gravityAlpha = 1.0f - std::exp(-dtSeconds / config::kGravityTauSeconds);
  const float dynamicAlpha = 1.0f - std::exp(
      -dtSeconds * 2.0f * 3.14159265f * config::kAccelerationLowPassHz);
  float accelerationEnergy = 0.0f;
  float gyroEnergy = 0.0f;
  for (unsigned i = 0; i < 3; ++i) {
    gravity_[i] += gravityAlpha * (sample.accelerationG[i] - gravity_[i]);
    const float highPass = sample.accelerationG[i] - gravity_[i];
    dynamic_[i] += dynamicAlpha * (highPass - dynamic_[i]);
    accelerationEnergy += dynamic_[i] * dynamic_[i] * 1000000.0f;
    if (sample.gyroValid) {
      gyroEnergy += sample.gyroDps[i] * sample.gyroDps[i];
    }
  }
  while (count_ && sample.atMs - window_[head_].atMs > config::kMotionWindowMs) {
    removeOldest();
  }
  if (count_ == kCapacity) {
    removeOldest();
  }
  EnergySample &entry = window_[(head_ + count_) % kCapacity];
  entry.atMs = sample.atMs;
  entry.acceleration = accelerationEnergy;
  entry.gyro = gyroEnergy;
  entry.gyroValid = sample.gyroValid;
  accelerationSum_ += accelerationEnergy;
  gyroSum_ += gyroEnergy;
  gyroSamples_ += sample.gyroValid ? 1 : 0;
  ++count_;
  lastSampleAt_ = sample.atMs;
  updateMovement(sample.atMs);
}

void MotionProcessor::updateMovement(uint32_t now) {
  if (!windowReady()) {
    entering_ = false;
    exiting_ = false;
    return;
  }
  const float rms = std::sqrt(std::max(accelerationSum_, 0.0f) / count_);
  if (!moving_) {
    if (rms >= config::kMotionEnterMg) {
      if (!entering_) {
        entering_ = true;
        enterAt_ = now;
      }
      if (now - enterAt_ >= config::kMotionEnterMs) {
        moving_ = true;
        entering_ = false;
      }
    } else {
      entering_ = false;
    }
  } else {
    if (rms <= config::kMotionExitMg) {
      if (!exiting_) {
        exiting_ = true;
        exitAt_ = now;
      }
      if (now - exitAt_ >= config::kMotionExitMs) {
        moving_ = false;
        exiting_ = false;
      }
    } else {
      exiting_ = false;
    }
  }
  if (moving_) {
    motionSeen_ = true;
    lastMotionAt_ = now;
  }
}

MotionSnapshot MotionProcessor::snapshot(uint32_t now) const {
  MotionSnapshot out;
  out.clipped = clippingSeen_ && now - lastClippingAt_ < config::kMotionWindowMs;
  out.samplesInWindow = static_cast<unsigned>(count_);
  out.valid = initialized_ && windowReady() && !out.clipped &&
              now - lastSampleAt_ <= config::kImuStaleMs;
  if (!out.valid) {
    return out;
  }
  out.gyroValid = gyroSamples_ == count_;
  out.moving = moving_;
  out.accelerationRmsMg = std::sqrt(std::max(accelerationSum_, 0.0f) / count_);
  if (out.gyroValid) {
    out.gyroRmsDps = std::sqrt(std::max(gyroSum_, 0.0f) / count_);
  }
  if (motionSeen_) {
    out.lastMotionAgeMs = static_cast<uint16_t>(
        std::min(now - lastMotionAt_, static_cast<uint32_t>(65534)));
  }
  return out;
}

}  // namespace brelock
