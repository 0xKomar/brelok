//! Bidirectional connection for the selected fob. Scanning remains independent:
//! Windows RSSI is accepted only from real advertisement events, never cached
//! properties read during a GATT telemetry poll.
use crate::ble::{RawAdvertisement, TransportEvent};
use anyhow::{Context, Result, bail};
use brelock_core::{
    DeviceId,
    control::{COMMAND_UUID, ControlRequest, HOST_STATUS_UUID, HostUpdate, TELEMETRY_UUID},
    decode_telemetry,
    protocol::COMPANY_ID,
};
use btleplug::{
    api::{Central, Peripheral as _, WriteType},
    platform::{Adapter, Peripheral},
};
use std::{
    future::Future,
    pin::Pin,
    time::{Duration, Instant},
};
use tokio::{
    sync::{mpsc, watch},
    time::{MissedTickBehavior, interval, sleep, timeout},
};
use uuid::Uuid;

pub async fn run_bridge(
    adapter: Adapter,
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    host: watch::Receiver<HostUpdate>,
    mut stop: watch::Receiver<bool>,
) {
    while !*stop.borrow() {
        let selected = host.borrow().device_id;
        if let Some(id) = selected {
            let peripherals = adapter.peripherals().await.unwrap_or_default();
            for peripheral in peripherals {
                let matches = peripheral
                    .properties()
                    .await
                    .ok()
                    .flatten()
                    .and_then(|p| {
                        p.manufacturer_data
                            .get(&COMPANY_ID)
                            .and_then(|bytes| decode_telemetry(bytes).ok())
                    })
                    .is_some_and(|packet| packet.device_id == id);
                if !matches {
                    continue;
                }
                let outcome =
                    device_session(peripheral.clone(), id, epoch, &events, &host, &mut stop).await;
                let _ = timeout(Duration::from_secs(2), peripheral.disconnect()).await;
                let _ = events
                    .send(TransportEvent::ControlLink {
                        device_id: id,
                        connected: false,
                        detail: outcome.err().map(|e| format!("{e:#}")),
                    })
                    .await;
                break;
            }
        }
        tokio::select! {
            _ = stop.changed() => break,
            _ = sleep(Duration::from_secs(2)) => {},
        }
    }
}
async fn device_session(
    peripheral: Peripheral,
    id: DeviceId,
    epoch: Instant,
    events: &mpsc::Sender<TransportEvent>,
    host: &watch::Receiver<HostUpdate>,
    stop: &mut watch::Receiver<bool>,
) -> Result<()> {
    timeout(Duration::from_secs(8), peripheral.connect())
        .await
        .context("connection timed out")??;
    timeout(Duration::from_secs(5), peripheral.discover_services())
        .await
        .context("GATT discovery timed out")??;
    let characteristics = peripheral.characteristics();
    let find = |uuid: &str| {
        characteristics
            .iter()
            .find(|c| c.uuid == Uuid::parse_str(uuid).unwrap())
            .cloned()
            .context("fob does not have the control service; update firmware")
    };
    let telemetry = find(TELEMETRY_UUID)?;
    let status = find(HOST_STATUS_UUID)?;
    let command = find(COMMAND_UUID)?;
    let initial = timeout(Duration::from_secs(1), peripheral.read(&telemetry)).await??;
    if decode_telemetry(&initial)?.device_id != id {
        bail!("GATT device ID mismatch");
    }
    events
        .send(TransportEvent::ControlLink {
            device_id: id,
            connected: true,
            detail: None,
        })
        .await?;
    let properties = peripheral.properties().await?;
    let name = properties.and_then(|p| p.local_name);
    let mut timer = interval(Duration::from_millis(200));
    timer.set_missed_tick_behavior(MissedTickBehavior::Skip);
    let mut last_command = None;
    let mut iteration = 0u64;
    let mut latest_payload = initial;
    // CoreBluetooth can delay RSSI callbacks. Keep exactly one pending read,
    // independently of GATT telemetry/status, rather than cancelling a slow
    // callback every 800 ms and starving the display and calibration.
    let mut rssi_request: Option<Pin<Box<dyn Future<Output = Result<i16>> + Send>>> = None;
    loop {
        tokio::select! {
            _ = stop.changed() => break,
            rssi = async {
                match rssi_request.as_mut() {
                    Some(request) => request.await,
                    None => std::future::pending().await,
                }
            } => {
                rssi_request = None;
                let rssi = rssi?;
                // This is a real radio measurement. Reusing the last telemetry
                // payload gives a duplicate sequence, so it cannot advance the
                // device heartbeat while supplying the new RSSI observation.
                events.send(TransportEvent::Advertisement {
                    advertisement: RawAdvertisement {
                        received_at: epoch.elapsed(), address: peripheral.id().to_string(),
                        name: name.clone(), rssi_dbm: Some(rssi), payload: latest_payload.clone(),
                    },
                }).await?;
            }
            _ = timer.tick() => {
                let update = *host.borrow();
                if update.device_id != Some(id) { break; }
                let payload = timeout(Duration::from_secs(1), peripheral.read(&telemetry)).await??;
                if decode_telemetry(&payload)?.device_id != id { bail!("GATT device changed ID"); }
                latest_payload = payload.clone();
                events.send(TransportEvent::Advertisement {
                    advertisement: RawAdvertisement {
                        received_at: epoch.elapsed(), address: peripheral.id().to_string(),
                        name: name.clone(), rssi_dbm: None, payload,
                    },
                }).await?;
                let bytes = timeout(Duration::from_secs(1), peripheral.read(&command)).await??;
                if let Ok(request) = ControlRequest::decode(&bytes)
                    && request.session == update.status.session
                    && last_command != Some(request) {
                    last_command = Some(request);
                    events.send(TransportEvent::Control { device_id: id, request }).await?;
                }
                if iteration.is_multiple_of(2) {
                    let bytes = update.status.encode();
                    timeout(Duration::from_secs(1),
                        peripheral.write(&status, &bytes, WriteType::WithResponse)).await??;
                }
                iteration = iteration.wrapping_add(1);
                if (cfg!(target_os = "macos") || cfg!(target_os = "android")) && rssi_request.is_none() {
                    let reader = peripheral.clone();
                    rssi_request = Some(Box::pin(async move {
                        timeout(Duration::from_secs(3), reader.read_rssi()).await
                            .context("RSSI callback timed out")?
                            .context("reading connected RSSI")
                    }));
                }
            }
        }
    }
    Ok(())
}
