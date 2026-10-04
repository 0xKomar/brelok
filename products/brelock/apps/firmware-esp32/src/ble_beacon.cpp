#include "ble_beacon.h"

#include <BLEDevice.h>
#include <BLE2902.h>
#include <esp_bt.h>

#include "config.h"

namespace brelock {

BleBeacon *BleBeacon::instance_ = nullptr;

bool BleBeacon::begin(const Telemetry &initial) {
  events_ = xQueueCreate(8, sizeof(GapResult));
  connections_ = xQueueCreate(1, sizeof(bool));
  hostUpdates_ = xQueueCreate(1, sizeof(HostStatus));
  if (!events_ || !connections_ || !hostUpdates_) {
    lastError_ = ESP_ERR_NO_MEM;
    ++errors_;
    return false;
  }
  instance_ = this;
  BLEDevice::init("breLock");
  BLEDevice::setMTU(64);
  auto *server = BLEDevice::createServer();
  server->setCallbacks(this);
  auto *service = server->createService(kServiceUuid);
  telemetryCharacteristic_ = service->createCharacteristic(
      kTelemetryUuid, BLECharacteristic::PROPERTY_READ);
  auto *status = service->createCharacteristic(kHostStatusUuid,
                                               BLECharacteristic::PROPERTY_WRITE);
  status->setCallbacks(this);
  commandCharacteristic_ = service->createCharacteristic(
      kCommandUuid, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
  commandCharacteristic_->addDescriptor(new BLE2902());
  std::array<uint8_t, 12> empty{};
  commandCharacteristic_->setValue(empty.data(), empty.size());
  service->start();
  BLEDevice::setCustomGapHandler(onGapEvent);
  const esp_err_t result = esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, BRELOCK_TX_POWER);
  if (result != ESP_OK) {
    fail(result, millis());
    return false;
  }
  parameters_.adv_int_min = BRELOCK_ADV_INTERVAL_MIN;
  parameters_.adv_int_max = BRELOCK_ADV_INTERVAL_MAX;
  // Accept the selected desktop, then retain non-connectable advertising while
  // connected. Windows obtains fresh RSSI from these scan events.
  parameters_.adv_type = ADV_TYPE_IND;
  parameters_.own_addr_type = BLE_ADDR_TYPE_PUBLIC;
  parameters_.channel_map = ADV_CHNL_ALL;
  parameters_.adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY;
  initialized_ = true;
  publish(initial);
  poll(millis());
  return true;
}

void BleBeacon::publish(const Telemetry &telemetry) {
  if (telemetryCharacteristic_) {
    auto bytes = encodeTelemetry(telemetry);
    telemetryCharacteristic_->setValue(bytes.data(), bytes.size());
  }
  pending_ = createPrimaryAdvertisement(telemetry);
  pendingSequence_ = telemetry.sequence;
  dirty_ = true;
}

void BleBeacon::onConnect(BLEServer *) {
  const bool value = true;
  xQueueOverwrite(connections_, &value);
}
void BleBeacon::onDisconnect(BLEServer *) {
  const bool value = false;
  xQueueOverwrite(connections_, &value);
}
void BleBeacon::onWrite(BLECharacteristic *characteristic) {
  const auto bytes = characteristic->getValue();
  HostStatus status;
  if (decodeHostStatus(reinterpret_cast<const uint8_t *>(bytes.data()), bytes.size(), status)) {
    status.receivedAtMs = millis();
    xQueueOverwrite(hostUpdates_, &status);
  }
}
bool BleBeacon::sendAction(DeviceAction action, uint32_t now) {
  if (!connected_ || !hostStatus_.fresh(now) || action == DeviceAction::None ||
      (commandSequence_ != 0 && hostStatus_.acknowledgedSequence != commandSequence_))
    return false;
  if (++commandSequence_ == 0) ++commandSequence_;
  auto bytes = encodeControl(action, commandSequence_, hostStatus_.session);
  commandCharacteristic_->setValue(bytes.data(), bytes.size());
  // The last action is readable until acknowledged, so a dropped notification
  // cannot lose a calibration/lock request (also fits the default ATT MTU).
  return true;
}

void BleBeacon::onGapEvent(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param) {
  if (!instance_ || !instance_->events_) {
    return;
  }
  GapResult result{};
  switch (event) {
    case ESP_GAP_BLE_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT:
      result.operation = Operation::ScanResponse;
      result.status = param->scan_rsp_data_raw_cmpl.status;
      break;
    case ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT:
      result.operation = Operation::Primary;
      result.status = param->adv_data_raw_cmpl.status;
      break;
    case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
      result.operation = Operation::Start;
      result.status = param->adv_start_cmpl.status;
      break;
    case ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT:
      result.operation = Operation::Stop;
      result.status = param->adv_stop_cmpl.status;
      break;
    default:
      return;
  }
  xQueueSend(instance_->events_, &result, 0);
}

void BleBeacon::fail(int error, uint32_t now) {
  lastError_ = error;
  ++errors_;
  operation_ = Operation::None;
  retryPending_ = true;
  retryAt_ = now;
  dirty_ = true;
}

void BleBeacon::poll(uint32_t now) {
  if (!initialized_) {
    return;
  }
  bool connection;
  if (xQueueReceive(connections_, &connection, 0) == pdTRUE) {
    connected_ = connection;
    if (connection) advertising_ = false;  // connect stops legacy advertising
    restartAdvertising_ = advertising_;
    parameters_.adv_type = connected_ ? ADV_TYPE_SCAN_IND : ADV_TYPE_IND;
    hostStatus_ = HostStatus{};
    commandSequence_ = 0;
    std::array<uint8_t, 12> empty{};
    commandCharacteristic_->setValue(empty.data(), empty.size());
  }
  HostStatus status;
  if (xQueueReceive(hostUpdates_, &status, 0) == pdTRUE && connected_) {
    if (hostStatus_.session != status.session) {
      commandSequence_ = 0;
      std::array<uint8_t, 12> empty{};
      commandCharacteristic_->setValue(empty.data(), empty.size());
    }
    hostStatus_ = status;
  }
  GapResult result{};
  while (xQueueReceive(events_, &result, 0) == pdTRUE) {
    if (result.operation != operation_) {
      continue;
    }
    operation_ = Operation::None;
    if (result.status != ESP_BT_STATUS_SUCCESS) {
      fail(result.status, now);
      continue;
    }
    if (result.operation == Operation::ScanResponse) {
      scanReady_ = true;
    } else if (result.operation == Operation::Primary) {
      dataReady_ = true;
      publishedSequence_ = inFlightSequence_;
      lastPublishAt_ = now;
      lastError_ = 0;
    } else if (result.operation == Operation::Start) {
      advertising_ = true;
      restartAdvertising_ = false;
    } else if (result.operation == Operation::Stop) {
      advertising_ = false;
      restartAdvertising_ = false;
    }
  }
  if (operation_ != Operation::None) {
    if (now - operationAt_ >= config::kBleOperationTimeoutMs) {
      fail(ESP_ERR_TIMEOUT, now);
    }
    return;
  }
  if (retryPending_) {
    if (now - retryAt_ < config::kBleRetryMs) {
      return;
    }
    retryPending_ = false;
  }

  esp_err_t error = ESP_OK;
  if (!scanReady_) {
    operation_ = Operation::ScanResponse;
    error = esp_ble_gap_config_scan_rsp_data_raw(scanResponse_.data(), scanResponse_.size());
  } else if (restartAdvertising_ && advertising_) {
    operation_ = Operation::Stop;
    error = esp_ble_gap_stop_advertising();
  } else if (dataReady_ && !advertising_) {
    operation_ = Operation::Start;
    error = esp_ble_gap_start_advertising(&parameters_);
  } else if (dirty_) {
    inFlight_ = pending_;
    inFlightSequence_ = pendingSequence_;
    dirty_ = false;
    operation_ = Operation::Primary;
    // Update in place; do not create a stop/start gap at every sensor summary.
    error = esp_ble_gap_config_adv_data_raw(inFlight_.data(), inFlight_.size());
  }
  operationAt_ = now;
  if (error != ESP_OK) {
    fail(error, now);
  }
}

bool BleBeacon::healthy(uint32_t now) const {
  return (advertising_ || connected_) && lastError_ == 0 &&
         now - lastPublishAt_ < config::kBleOperationTimeoutMs;
}

}  // namespace brelock
