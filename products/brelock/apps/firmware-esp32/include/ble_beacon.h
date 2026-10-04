#pragma once

#include <Arduino.h>
#include <esp_gap_ble_api.h>
#include <BLEServer.h>
#include "control.h"

#include "telemetry.h"

namespace brelock {

// GAP events are delivered by the Bluetooth task; all publishing stays in loop.
class BleBeacon : private BLEServerCallbacks, private BLECharacteristicCallbacks {
 public:
  bool begin(const Telemetry &initial);
  void publish(const Telemetry &telemetry);
  void poll(uint32_t now);
  bool healthy(uint32_t now) const;
  uint32_t publishedSequence() const { return publishedSequence_; }
  uint32_t errors() const { return errors_; }
  int lastError() const { return lastError_; }
  bool connected() const { return connected_; }
  const HostStatus &hostStatus() const { return hostStatus_; }
  bool sendAction(DeviceAction action, uint32_t now);

 private:
  enum class Operation : uint8_t { None, ScanResponse, Primary, Start, Stop };
  struct GapResult {
    Operation operation;
    uint8_t status;
  };
  static BleBeacon *instance_;
  static void onGapEvent(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param);
  QueueHandle_t events_ = nullptr;
  QueueHandle_t connections_ = nullptr;
  QueueHandle_t hostUpdates_ = nullptr;
  BLECharacteristic *telemetryCharacteristic_ = nullptr;
  BLECharacteristic *commandCharacteristic_ = nullptr;
  HostStatus hostStatus_;
  bool connected_ = false;
  bool restartAdvertising_ = false;
  uint16_t commandSequence_ = 0;
  ScanResponse scanResponse_ = createScanResponse();
  PrimaryAdvertisement pending_{};
  PrimaryAdvertisement inFlight_{};
  uint32_t pendingSequence_ = 0;
  uint32_t inFlightSequence_ = 0;
  uint32_t publishedSequence_ = 0;
  bool dirty_ = false;
  bool scanReady_ = false;
  bool dataReady_ = false;
  bool advertising_ = false;
  bool initialized_ = false;
  Operation operation_ = Operation::None;
  uint32_t operationAt_ = 0;
  uint32_t retryAt_ = 0;
  bool retryPending_ = false;
  uint32_t lastPublishAt_ = 0;
  uint32_t errors_ = 0;
  int lastError_ = 0;
  esp_ble_adv_params_t parameters_{};

  void fail(int error, uint32_t now);
  void onConnect(BLEServer *) override;
  void onDisconnect(BLEServer *) override;
  void onWrite(BLECharacteristic *) override;
};

}  // namespace brelock
