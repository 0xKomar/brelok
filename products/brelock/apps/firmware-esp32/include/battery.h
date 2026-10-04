#pragma once

#include <cstdint>

namespace brelock {

struct BatterySnapshot {
  bool valid = false;
  bool low = false;
  uint16_t millivolts = 0;
};

class BatteryMonitor {
 public:
  void begin();
  void update();
  BatterySnapshot snapshot() const { return snapshot_; }

 private:
  bool filterInitialized_ = false;
  float filteredMv_ = 0.0f;
  BatterySnapshot snapshot_;
};

}  // namespace brelock
