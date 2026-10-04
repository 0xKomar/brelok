#include "battery.h"

#include <Arduino.h>

#include "board_pins.h"
#include "config.h"
#include "telemetry.h"

namespace brelock {

void BatteryMonitor::begin() {
  pinMode(board::kBatteryAdc, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(board::kBatteryAdc, ADC_11db);
  update();
}

void BatteryMonitor::update() {
  uint32_t adcSum = 0;
  for (unsigned i = 0; i < 8; ++i) {
    adcSum += analogReadMilliVolts(board::kBatteryAdc);
  }
  const float mv = adcSum / 8.0f * config::kBatteryDivider *
                   config::kBatteryCalibrationGain + config::kBatteryCalibrationOffsetMv;
  snapshot_ = BatterySnapshot{};
  if (mv < config::kBatteryMinMv || mv > config::kBatteryMaxMv) {
    filterInitialized_ = false;
    return;
  }
  filteredMv_ = filterInitialized_ ? filteredMv_ + 0.25f * (mv - filteredMv_) : mv;
  filterInitialized_ = true;
  snapshot_.valid = true;
  snapshot_.millivolts = quantizeU16(filteredMv_);
  snapshot_.low = snapshot_.millivolts <= config::kBatteryLowMv;
}

}  // namespace brelock
