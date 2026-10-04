#pragma once
#include <Adafruit_GFX.h>
#include "device_ui.h"
namespace brelock {
struct UiRenderState {
  UiPage page = UiPage::Protection;
  HostStatus host;
  bool online = false, bleHealthy = false, touchReady = false;
  bool moving = false, imuValid = false;
  uint16_t batteryMv = 0;
  uint8_t holdPercent = 0;
};
void renderDeviceUi(Adafruit_GFX &canvas, const UiRenderState &state);
}  // namespace brelock
