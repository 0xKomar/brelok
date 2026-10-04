#pragma once

// Waveshare ESP32-S3-Touch-LCD-1.28 (Touch, not the LCD-only board).
// Pin map verified against the manufacturer's DEV_Config.h example.
namespace brelock {
namespace board {

constexpr int kSda = 6;
constexpr int kScl = 7;
constexpr int kBatteryAdc = 1;
constexpr int kLcdDc = 8;
constexpr int kLcdCs = 9;
constexpr int kLcdSclk = 10;
constexpr int kLcdMosi = 11;
constexpr int kLcdMiso = 12;
constexpr int kLcdReset = 14;
constexpr int kBacklight = 2;
constexpr int kTouchInterrupt = 5;
constexpr int kTouchReset = 13;

}  // namespace board
}  // namespace brelock
