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
