#pragma once
#include "control.h"
namespace brelock {
enum class UiPage : uint8_t { Protection, Distance, Calibration, Lock };
class DeviceUi {
 public:
  void touch(uint32_t now, bool down, int16_t x, int16_t y, uint8_t gesture,
             const HostStatus &host);
  void tick(uint32_t now, const HostStatus &host);
  bool syncHost(uint32_t now, const HostStatus &host);
  void cancelTouch();
  UiPage page() const { return page_; }
  bool touching() const { return down_; }
  uint8_t holdPercent(uint32_t now) const;
  DeviceAction takeAction();
 private:
  UiPage page_ = UiPage::Protection;
  bool down_ = false;
  bool moved_ = false;
  bool swiped_ = false;
  bool holdEligible_ = false;
  bool fired_ = false;
  uint32_t pressedAt_ = 0;
  uint64_t pressSession_ = 0;
  DeviceAction holdAction_ = DeviceAction::None;
  uint8_t pressCalibration_ = 0;
  uint8_t pressStep_ = 0;
  uint8_t hostStep_ = 0;
  uint64_t hostSession_ = 0;
  int16_t startX_ = 0;
  int16_t startY_ = 0;
  DeviceAction pending_ = DeviceAction::None;
  uint8_t lastReleasedGesture_ = 0;
  void swipe(bool left);
};
}  // namespace brelock
