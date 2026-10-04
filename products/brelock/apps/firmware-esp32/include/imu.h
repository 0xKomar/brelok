#pragma once

#include <cstdint>

#include "motion.h"

namespace brelock {

enum class ImuReadResult { NotReady, Sample, Error };

class ImuDriver {
 public:
  bool begin();
  ImuReadResult poll(ImuSample &out);
  bool initialized() const { return initialized_; }
  uint8_t address() const { return address_; }
  uint8_t whoAmI() const { return whoAmI_; }
  uint8_t revision() const { return revision_; }
  uint32_t sampleCounter() const { return lastCounter_; }
  uint32_t errors() const { return errors_; }

 private:
  uint8_t address_ = 0;
  uint8_t whoAmI_ = 0;
  uint8_t revision_ = 0;
  bool initialized_ = false;
  bool counterKnown_ = false;
  uint32_t lastCounter_ = 0;
  uint32_t errors_ = 0;
};

}  // namespace brelock
