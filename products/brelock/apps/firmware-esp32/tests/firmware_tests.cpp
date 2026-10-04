#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

#include "motion.h"
#include "telemetry.h"

namespace {

unsigned checks = 0;

void expect(bool condition, const char *message) {
  ++checks;
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

brelock::ImuSample sample(uint32_t at, float dynamicG = 0.0f) {
  brelock::ImuSample out;
  out.atMs = at;
  out.accelerationG = {{0.0f, 0.0f, 1.0f + dynamicG}};
  out.gyroDps = {{3.0f, 4.0f, 0.0f}};
  out.gyroValid = true;
  return out;
}

uint32_t feed(brelock::MotionProcessor &processor, uint32_t start,
              unsigned durationMs, float amplitudeG = 0.0f) {
  uint32_t last = start;
  for (unsigned elapsed = 0; elapsed <= durationMs; elapsed += 16) {
    last = start + elapsed;
    const float acceleration = amplitudeG * std::sin(
        2.0f * 3.14159265f * 2.0f * elapsed / 1000.0f);
    processor.push(sample(last, acceleration));
  }
  return last;
}

void testPacket() {
  brelock::Telemetry t;
  t.deviceId = {{0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC}};
  t.bootId = 0x1234;
  t.sequence = 0x89ABCDEF;
  t.moving = true;
  t.imuValid = true;
  t.gyroValid = true;
  t.batteryValid = true;
  t.accelerationRmsMg = 123;
  t.gyroRmsDeciDps = 456;
  t.lastMotionAgeMs = 789;
  t.batteryMv = 4000;
  t.nominalTxDbm = -3;
  const brelock::TelemetryPayload expected = {{
      3, 1, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0x34, 0x12,
      0xEF, 0xCD, 0xAB, 0x89, 0x17, 0x7B, 0, 0xC8, 1, 0x15, 3,
      0xA0, 0x0F, 0x00}};
  expect(brelock::encodeTelemetry(t) == expected,
         "wire format must match the v3 packet, including byte order and units");
  const auto primary = brelock::createPrimaryAdvertisement(t);
  expect(primary.size() == 31, "primary advertisement must fit legacy BLE");
  expect(primary[3] == 27 && primary[4] == 0xFF && primary[5] == 0xFF && primary[6] == 0xFF,
         "manufacturer AD structure must include the 0xFFFF test company ID");
  expect(std::equal(expected.begin(), expected.end(), primary.begin() + 7),
         "full identity and sensor data must be in the primary packet");
  t.buttonEventActive = true;
  t.buttonEventCount = 42;
  const auto marked = brelock::encodeTelemetry(t);
  expect((marked[14] & brelock::kButtonEvent) != 0 && marked[23] == 42,
         "touch marker must be latched in v3 flags with a monotonic wrapping counter");
  t.buttonEventActive = false;
  const auto response = brelock::createScanResponse();
  const std::vector<uint8_t> serviceUuid = {
      0x43, 0x4F, 0x4C, 0x45, 0x52, 0x4B, 0x21, 0x9C,
      0x8A, 0x4D, 0x7F, 0x6F, 0x00, 0xA1, 0x20, 0x9E};
  expect(response.size() == 27 && response[0] == 17 && response[1] == 7,
         "scan response must contain a complete 128-bit service UUID");
  expect(std::equal(serviceUuid.begin(), serviceUuid.end(), response.begin() + 2),
         "service UUID must use BLE byte order");
  unsigned cursor = 0;
  while (cursor < response.size()) {
    const unsigned length = response[cursor];
    expect(length > 0 && cursor + 1 + length <= response.size(),
           "scan response AD lengths must be valid");
    cursor += length + 1;
  }
  expect(cursor == response.size(), "scan response must not contain incomplete AD data");

  t.imuValid = false;
  auto invalid = brelock::encodeTelemetry(t);
  expect(invalid[14] == brelock::kBatteryValid,
         "invalid IMU must not advertise movement or valid gyro");
  expect(invalid[15] == 0 && invalid[17] == 0 && invalid[19] == 255 && invalid[20] == 255,
         "invalid IMU must carry zero RMS and unknown movement age");
  t.imuValid = true;
  t.clipped = true;
  t.batteryValid = false;
  invalid = brelock::encodeTelemetry(t);
  expect(invalid[14] == brelock::kClipped && invalid[21] == 0 && invalid[22] == 0,
         "clipping and invalid battery must not be reported as healthy data");
  t.clipped = false;
  t.gyroValid = false;
  invalid = brelock::encodeTelemetry(t);
  expect((invalid[14] & brelock::kImuValid) && !(invalid[14] & brelock::kGyroValid),
         "accelerometer remains usable without gyro");
  expect(invalid[17] == 0 && invalid[18] == 0, "invalid gyro must have no RMS value");
  t.sequence = std::numeric_limits<uint32_t>::max();
  ++t.sequence;
  const auto wrapped = brelock::encodeTelemetry(t);
  expect(wrapped[10] == 0 && wrapped[11] == 0 && wrapped[12] == 0 && wrapped[13] == 0,
         "sequence must wrap as an unsigned 32-bit counter");
}

void testQuantization() {
  expect(brelock::quantizeU16(12.49f) == 12 && brelock::quantizeU16(12.51f) == 13,
         "sensor units must round to the nearest representable value");
  expect(brelock::quantizeU16(-1.0f) == 0, "negative magnitudes must not underflow");
  expect(brelock::quantizeU16(90000.0f) == 65535, "large values must saturate");
  expect(brelock::quantizeU16(std::numeric_limits<float>::quiet_NaN()) == 0,
         "NaN must not become an arbitrary integer");
  expect(brelock::quantizeU16(std::numeric_limits<float>::infinity()) == 0,
         "infinite values must not become a valid magnitude");
}

void testStationaryAndRotation() {
  brelock::MotionProcessor p;
  expect(!p.snapshot(0).valid, "empty history must be unknown, not still");
  feed(p, 0, 760);
  expect(!p.snapshot(752).valid, "an incomplete window must remain in warmup");
  const uint32_t at = feed(p, 768, 3200);
  auto out = p.snapshot(at);
  expect(out.valid && !out.moving, "gravity at rest must not count as motion");
  expect(out.accelerationRmsMg < 0.1f, "stationary gravity must be removed");
  expect(out.gyroValid && std::fabs(out.gyroRmsDps - 5.0f) < 0.01f,
         "gyro RMS is the three-axis magnitude in degrees per second");
  expect(out.lastMotionAgeMs == brelock::kUnknownMotionAge,
         "a device with no confirmed motion must advertise the sentinel");
  expect(!p.snapshot(at + 101).valid, "old samples must not remain valid indefinitely");

  brelock::MotionProcessor orientation;
  for (unsigned i = 0; i < 160; ++i) {
    auto s = sample(i * 16);
    s.accelerationG = {{1.0f, 0.0f, 0.0f}};
    s.gyroDps = {{0.0f, 0.0f, 100.0f}};
    orientation.push(s);
  }
  out = orientation.snapshot(159 * 16);
  expect(out.valid && !out.moving, "a fixed orientation and gyro alone must not set motion");
  expect(std::fabs(out.gyroRmsDps - 100.0f) < 0.01f, "gyro remains diagnostic data");
}

void testObservedBoardSamplingRate() {
  brelock::MotionProcessor p;
  for (uint32_t at = 0; at <= 1200; at += 22) {
    p.push(sample(at, 0.02f));
  }
  const auto out = p.snapshot(1188);
  expect(out.valid && out.samplesInWindow >= 40,
         "the measured ~46 Hz board cadence must provide a valid RMS window");
}

void testMovementAndExit() {
  brelock::MotionProcessor p;
  uint32_t at = feed(p, 0, 4000, 0.2f);
  auto out = p.snapshot(at);
  expect(out.valid && out.moving, "sustained walking-like acceleration must confirm activity");
  expect(out.accelerationRmsMg > 60.0f && out.accelerationRmsMg < 200.0f,
         "filtered acceleration must use mg, not raw g or ADC units");
  expect(out.lastMotionAgeMs == 0, "confirmed activity must keep motion age current");
  at = feed(p, at + 16, 4000);
  out = p.snapshot(at);
  expect(out.valid && !out.moving, "activity must exit after quiet data and hysteresis");
  expect(out.lastMotionAgeMs > 1500 && out.lastMotionAgeMs < 4000,
         "quiet data must age the last activity without erasing its history");
  at = feed(p, at + 16, 70000);
  out = p.snapshot(at);
  expect(out.lastMotionAgeMs == 65534, "old activity age must saturate below the unknown sentinel");
}

void testNoiseAndSpikes() {
  brelock::MotionProcessor p;
  const uint32_t at = feed(p, 0, 5000, 0.004f);
  const auto out = p.snapshot(at);
  expect(out.valid && !out.moving && out.accelerationRmsMg < 10.0f,
         "small stationary noise must not become activity");

  brelock::MotionProcessor spike;
  uint32_t time = feed(spike, 0, 2000);
  spike.push(sample(time + 16, 0.05f));
  time = feed(spike, time + 32, 2000);
  expect(!spike.snapshot(time).moving, "one small disturbance must not bypass motion dwell time");
}

void testInvalidationAndRecovery() {
  brelock::MotionProcessor p;
  uint32_t at = feed(p, 0, 3000, 0.2f);
  expect(p.snapshot(at).moving, "test precondition: movement is confirmed");
  auto bad = sample(at + 16);
  bad.clipped = true;
  p.push(bad);
  auto out = p.snapshot(bad.atMs);
  expect(!out.valid && !out.moving && out.clipped,
         "clipping must immediately make motion unknown");
  expect(out.lastMotionAgeMs == brelock::kUnknownMotionAge,
         "invalid motion history must not masquerade as recent activity");
  at = feed(p, bad.atMs + 16, 1600);
  out = p.snapshot(at);
  expect(out.valid && !out.clipped && !out.moving, "valid data must recover without a reboot");
  p.invalidate();
  expect(!p.snapshot(at).valid, "bus failure must invalidate previously healthy samples");
  at = feed(p, at + 16, 1400);
  bad = sample(at + 16);
  bad.accelerationG[0] = std::numeric_limits<float>::quiet_NaN();
  p.push(bad);
  expect(!p.snapshot(bad.atMs).valid, "non-finite input must be unknown");

  brelock::MotionProcessor gap;
  at = feed(gap, 0, 2000);
  gap.push(sample(at + 200));
  expect(!gap.snapshot(at + 200).valid, "a sampling gap must require a fresh window");

  brelock::MotionProcessor noGyro;
  for (unsigned i = 0; i < 100; ++i) {
    auto s = sample(i * 16);
    s.gyroValid = false;
    s.gyroDps[0] = std::numeric_limits<float>::quiet_NaN();
    noGyro.push(s);
  }
  out = noGyro.snapshot(99 * 16);
  expect(out.valid && !out.gyroValid && out.gyroRmsDps == 0.0f,
         "unavailable gyro must not disable a healthy accelerometer");
}

void testDuplicatesAndTimerWrap() {
  brelock::MotionProcessor duplicate;
  for (unsigned i = 0; i < 1000; ++i) {
    duplicate.push(sample(0, 0.2f));
  }
  expect(!duplicate.snapshot(0).valid && duplicate.snapshot(0).samplesInWindow == 1,
         "duplicate samples must not manufacture a valid window");

  brelock::MotionProcessor wrap;
  const uint32_t start = std::numeric_limits<uint32_t>::max() - 500;
  const uint32_t at = feed(wrap, start, 3000, 0.2f);
  expect(wrap.snapshot(at).valid && wrap.snapshot(at).moving,
         "millis wrap must not break the window or activity confirmation");
  expect(!wrap.snapshot(at + 101).valid, "freshness must also work after millis wrap");
}

}  // namespace

int main() {
  testPacket();
  testQuantization();
  testStationaryAndRotation();
  testObservedBoardSamplingRate();
  testMovementAndExit();
  testNoiseAndSpikes();
  testInvalidationAndRecovery();
  testDuplicatesAndTimerWrap();
  std::cout << "PASS: " << checks << " firmware checks (protocol and motion)\n";
}
