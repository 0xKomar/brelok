#pragma once

// Prefix widoczny podczas skanowania w aplikacji breLock.
#define BRELOCK_NAME_PREFIX "breLock"

// Moc reklam BLE. P3 to rozsądny punkt startowy do pomiarów odległości.
// Zbyt duża moc zwiększa zasięg i może pogorszyć użyteczność RSSI jako granicy.
#define BRELOCK_TX_POWER ESP_PWR_LVL_P3

// 64 jednostki BLE = 40 ms, 96 jednostek = 60 ms.
// Wyższa częstotliwość daje detektorowi trendu więcej próbek podczas ruchu.
#define BRELOCK_ADV_INTERVAL_MIN 64
#define BRELOCK_ADV_INTERVAL_MAX 96

#define BRELOCK_HEARTBEAT_MS 1000
#define BRELOCK_STATUS_LOG_MS 10000

#ifndef BRELOCK_DEBUG
#define BRELOCK_DEBUG 0
#endif

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

#ifdef BRELOCK_WAVESHARE
// Keep the original timing for the legacy esp32dev beacon.
#undef BRELOCK_ADV_INTERVAL_MIN
#undef BRELOCK_ADV_INTERVAL_MAX
#define BRELOCK_ADV_INTERVAL_MIN 160  // 100 ms in 0.625 ms units.
#define BRELOCK_ADV_INTERVAL_MAX 160
#endif

namespace brelock {
namespace config {

constexpr char kFirmwareVersion[] = "0.6.0-poc";
constexpr unsigned kTelemetryMs = 200;
constexpr unsigned kStatusMs = 1000;
constexpr unsigned kBatteryMs = 1000;
constexpr unsigned kImuPollUs = 4000;
constexpr unsigned kImuRetryMs = 2000;
constexpr unsigned kImuStaleMs = 100;
constexpr unsigned kI2cClockHz = 400000;
constexpr unsigned kI2cTimeoutMs = 5;
constexpr bool kGyroEnabled = true;

// START hypotheses, to be calibrated with recordings from the actual board.
constexpr unsigned kMotionWindowMs = 1000;
// The board yields about 46 new samples/s in the running PoC, so require
// 40 observations spanning at least 840 ms of this 1 s RMS window.
constexpr unsigned kMotionMinSamples = 40;
constexpr unsigned kMotionMinSpanMs = 840;
constexpr unsigned kMotionEnterMs = 200;
constexpr unsigned kMotionExitMs = 1500;
constexpr float kMotionEnterMg = 60.0f;
constexpr float kMotionExitMg = 35.0f;
constexpr float kGravityTauSeconds = 0.8f;
constexpr float kAccelerationLowPassHz = 8.0f;

constexpr float kBatteryDivider = 3.0f;
constexpr float kBatteryCalibrationGain = 1.0f;
constexpr float kBatteryCalibrationOffsetMv = 0.0f;
constexpr unsigned kBatteryMinMv = 2500;
constexpr unsigned kBatteryMaxMv = 4500;
constexpr unsigned kBatteryLowMv = 3500;

constexpr unsigned kDisplayMs = 500;
constexpr unsigned kTouchDebounceMs = 450;
constexpr unsigned kButtonEventMs = 3000;
#if BRELOCK_DEBUG
// Keep the display visible during calibration. Zero disables automatic blanking.
constexpr unsigned kDisplayIdleMs = 60000;
#else
constexpr unsigned kDisplayIdleMs = 10000;
#endif
constexpr unsigned kBleOperationTimeoutMs = 1000;
constexpr unsigned kBleRetryMs = 1000;

}  // namespace config
}  // namespace brelock
