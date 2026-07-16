#include <Arduino.h>
#include <BLEAdvertising.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <esp_bt.h>

#include "config.h"

namespace {

constexpr char kServiceUuid[] = "9e20a100-6f7f-4d8a-9c21-4b52454c4f43";
constexpr char kIdentityCharacteristicUuid[] = "9e20a101-6f7f-4d8a-9c21-4b52454c4f43";
constexpr uint8_t kProtocolVersion = 1;
constexpr uint8_t kDeviceTypeKeyfob = 1;

BLEAdvertising *advertising = nullptr;
std::string deviceName;
std::string deviceId;
bool clientConnected = false;
uint32_t lastHeartbeatAt = 0;
uint32_t lastStatusLogAt = 0;
bool ledState = false;

#if BRELOCK_DEBUG
#define DEBUG_PRINTLN(value) Serial.println(value)
#define DEBUG_PRINTF(format, ...) Serial.printf(format, ##__VA_ARGS__)
#else
#define DEBUG_PRINTLN(value) ((void)0)
#define DEBUG_PRINTF(format, ...) ((void)0)
#endif

std::string createDeviceId() {
  const uint64_t chipId = ESP.getEfuseMac();
  char buffer[13] = {};
  snprintf(buffer, sizeof(buffer), "%012llX", chipId & 0xFFFFFFFFFFFFULL);
  return std::string(buffer);
}

std::string createManufacturerData() {
  // 0xFFFF is reserved for development/testing. Replace it with an assigned
  // Bluetooth SIG company identifier before commercial distribution.
  uint8_t payload[] = {
      0xFF,
      0xFF,
      kProtocolVersion,
      kDeviceTypeKeyfob,
      0, 0, 0, 0, 0, 0,
  };
  for (size_t index = 0; index < 6; ++index) {
    payload[4 + index] = static_cast<uint8_t>(
        strtoul(deviceId.substr(index * 2, 2).c_str(), nullptr, 16));
  }

  return std::string(reinterpret_cast<const char *>(payload), sizeof(payload));
}

class ServerCallbacks final : public BLEServerCallbacks {
 public:
  void onConnect(BLEServer *) override {
    clientConnected = true;
    digitalWrite(LED_BUILTIN, HIGH);
    DEBUG_PRINTLN("[BLE] Klient połączony");
  }

  void onDisconnect(BLEServer *server) override {
    clientConnected = false;
    DEBUG_PRINTLN("[BLE] Klient rozłączony, wznawiam reklamy");
    delay(100);
    server->startAdvertising();
  }
};

void configureAdvertising(BLEServer *server) {
  advertising = server->getAdvertising();
  advertising->setMinInterval(BRELOCK_ADV_INTERVAL_MIN);
  advertising->setMaxInterval(BRELOCK_ADV_INTERVAL_MAX);
  advertising->setScanResponse(true);

  // Primary packet stays small and is available without an active scan.
  BLEAdvertisementData advertisementData;
  advertisementData.setFlags(0x06);  // General discoverable, no Classic BT.
  advertisementData.setCompleteServices(BLEUUID(kServiceUuid));
  advertising->setAdvertisementData(advertisementData);

  // Scan response: short name + full 48-bit identity + TX power = 31 bytes.
  BLEAdvertisementData scanResponseData;
  scanResponseData.setName(deviceName);
  scanResponseData.setManufacturerData(createManufacturerData());
  // AD structure: length, TX Power type (0x0A), calibrated value (+3 dBm).
  scanResponseData.addData(std::string("\x02\x0A\x03", 3));
  advertising->setScanResponseData(scanResponseData);
}

void printBootDiagnostics() {
  DEBUG_PRINTLN("");
  DEBUG_PRINTLN("========================================");
  DEBUG_PRINTLN(" breLock ESP32 beacon");
  DEBUG_PRINTLN("========================================");
  DEBUG_PRINTF("[ID] Nazwa:       %s\n", deviceName.c_str());
  DEBUG_PRINTF("[ID] Device ID:   %s\n", deviceId.c_str());
  DEBUG_PRINTF("[ID] BLE address: %s\n", BLEDevice::getAddress().toString().c_str());
  DEBUG_PRINTF("[BLE] Service:    %s\n", kServiceUuid);
  DEBUG_PRINTF("[BLE] Interwał:   %.1f–%.1f ms\n",
               BRELOCK_ADV_INTERVAL_MIN * 0.625,
               BRELOCK_ADV_INTERVAL_MAX * 0.625);
  DEBUG_PRINTLN("[BLE] Reklamowanie aktywne");
}

void updateHeartbeat(uint32_t now) {
  if (clientConnected) {
    digitalWrite(LED_BUILTIN, HIGH);
    return;
  }

  if (now - lastHeartbeatAt >= BRELOCK_HEARTBEAT_MS) {
    lastHeartbeatAt = now;
    ledState = !ledState;
    digitalWrite(LED_BUILTIN, ledState ? HIGH : LOW);
  }
}

void logStatus(uint32_t now) {
  if (now - lastStatusLogAt < BRELOCK_STATUS_LOG_MS) {
    return;
  }
  lastStatusLogAt = now;
  DEBUG_PRINTF("[STATUS] uptime=%lus, heap=%uB, client=%s\n",
               now / 1000UL,
               ESP.getFreeHeap(),
               clientConnected ? "connected" : "none");
}

}  // namespace

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(115200);
  delay(250);

  deviceId = createDeviceId();
  deviceName = std::string(BRELOCK_NAME_PREFIX) + "-" + deviceId.substr(6);

  BLEDevice::init(deviceName);

  BLEDevice::setPower(BRELOCK_TX_POWER, ESP_BLE_PWR_TYPE_ADV);

  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

  BLEService *service = server->createService(kServiceUuid);
  BLECharacteristic *identity = service->createCharacteristic(
      kIdentityCharacteristicUuid,
      BLECharacteristic::PROPERTY_READ);
  const std::string identityValue =
      std::string("brelock:v") + std::to_string(kProtocolVersion) + ":" + deviceId;
  identity->setValue(identityValue);
  service->start();

  configureAdvertising(server);
  advertising->start();
  printBootDiagnostics();
}

void loop() {
  const uint32_t now = millis();
  updateHeartbeat(now);
  logStatus(now);
  delay(10);
}
