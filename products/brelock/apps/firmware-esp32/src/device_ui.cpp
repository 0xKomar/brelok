#include "device_ui.h"
#include <cstdlib>
namespace brelock {
namespace {
bool inButton(int16_t x, int16_t y) {
  const int32_t dx = x - 120, dy = y - 112;
  return dx * dx + dy * dy <= 70 * 70;
}
}
void DeviceUi::swipe(bool left) {
  const unsigned page = static_cast<unsigned>(page_);
  page_ = static_cast<UiPage>((page + (left ? 1 : 3)) % 4);
  swiped_ = true;
  holdEligible_ = false;
}
void DeviceUi::touch(uint32_t now, bool down, int16_t x, int16_t y,
                     uint8_t gesture, const HostStatus &host) {
  syncHost(now,host);
  if (down && !down_) {
    lastReleasedGesture_ = 0;
    down_ = true;
    moved_ = swiped_ = fired_ = false;
    startX_ = x; startY_ = y; pressedAt_ = now;
    pressSession_ = host.session;
    pressCalibration_ = host.calibration;
    pressStep_ = host.calibrationStep;
    holdAction_ = DeviceAction::None;
    if (inButton(x, y) && host.fresh(now)) {
      if (page_ == UiPage::Lock && host.lockAvailable())
        holdAction_ = DeviceAction::LockNow;
      else if (page_ == UiPage::Calibration && host.calibration != 4 && host.calibration != 5)
        holdAction_ = (host.calibration == 1 || host.calibration == 3)
                          ? DeviceAction::SaveCalibration : DeviceAction::StartCalibration;
    }
    holdEligible_ = holdAction_ != DeviceAction::None;
  }
  if (down_) {
    const int dx = x - startX_, dy = y - startY_;
    if (std::abs(dx) > 22 || std::abs(dy) > 22) {
      moved_ = true;
      holdEligible_ = false;
    }
    if (!swiped_ && ((std::abs(dx) >= 50 && std::abs(dx) > std::abs(dy) * 2) ||
                    gesture == 3 || gesture == 4)) {
      swipe(gesture == 3 || (gesture != 4 && dx < 0));
    }
    if (down) tick(now, host);
  } else if ((gesture == 3 || gesture == 4) && gesture != lastReleasedGesture_) {
    // Some CST816S firmware reports only a final gesture, without a down frame.
    swipe(gesture == 3);
  }
  if (!down && down_) {
    down_ = false;
    holdEligible_ = false;
  }
  if (!down) lastReleasedGesture_ = gesture;
}
bool DeviceUi::syncHost(uint32_t now, const HostStatus &host) {
  if (host.fresh(now) && host.calibrationStep != 0 &&
      (host.calibration == 1 || host.calibration == 3 || host.calibration == 4 || host.calibration == 5) &&
      (hostStep_ != host.calibrationStep || hostSession_ != host.session)) {
    page_ = UiPage::Calibration;
    cancelTouch();
    hostStep_ = host.calibrationStep; hostSession_ = host.session;
    return true;
  }
  if (host.fresh(now) && host.calibration == 0) hostStep_ = 0;
  return false;
}
void DeviceUi::tick(uint32_t now, const HostStatus &host) {
  syncHost(now,host);
  const bool allowed = holdAction_ == DeviceAction::LockNow ? host.lockAvailable()
      : holdAction_ != DeviceAction::None && host.calibration == pressCalibration_
        && host.calibrationStep == pressStep_;
  if (!host.fresh(now) || !allowed || host.session != pressSession_)
    holdEligible_ = false;
  if (down_ && holdEligible_ && !fired_ && now - pressedAt_ >= 3000) {
    pending_ = holdAction_;
    fired_ = true;
    holdEligible_ = false;
  }
}
uint8_t DeviceUi::holdPercent(uint32_t now) const {
  if (fired_ && down_) return 100;
  if (!down_ || !holdEligible_) return 0;
  const uint32_t progress = (now - pressedAt_) / 30;
  return static_cast<uint8_t>(progress > 100 ? 100 : progress);
}
DeviceAction DeviceUi::takeAction() {
  const auto action = pending_;
  pending_ = DeviceAction::None;
  return action;
}
void DeviceUi::cancelTouch() {
  down_ = holdEligible_ = false;
  moved_ = true;
}
}  // namespace brelock
