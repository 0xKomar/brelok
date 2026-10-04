use anyhow::{Context, Result, bail};
use brelock_core::protocol::{COMPANY_ID, SERVICE_UUID};
use brelock_core::{
    DeviceId,
    control::{ControlRequest, HostUpdate},
};
use btleplug::{
    api::{Central, CentralEvent, CentralState, Manager as _, Peripheral as _, ScanFilter},
    platform::Manager,
};
use futures_util::StreamExt;
use serde::Serialize;
use std::time::{Duration, Instant};
use tokio::{
    sync::{mpsc, watch},
    time::timeout,
};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize)]
pub struct RawAdvertisement {
    #[serde(serialize_with = "duration_seconds")]
    pub received_at: Duration,
    pub address: String,
    pub name: Option<String>,
    pub rssi_dbm: Option<i16>,
    pub payload: Vec<u8>,
}

fn duration_seconds<S: serde::Serializer>(
    duration: &Duration,
    serializer: S,
) -> std::result::Result<S::Ok, S::Error> {
    serializer.serialize_f64(duration.as_secs_f64())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TransportState {
    Starting,
    Scanning,
    Demo,
    Unavailable,
    Stopped,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum TransportEvent {
    Status {
        state: TransportState,
        detail: Option<String>,
    },
    Advertisement {
        advertisement: RawAdvertisement,
    },
    ControlLink {
        device_id: DeviceId,
        connected: bool,
        detail: Option<String>,
    },
    Control {
        device_id: DeviceId,
        request: ControlRequest,
    },
}

async fn emit(
    events: &mpsc::Sender<TransportEvent>,
    event: TransportEvent,
    stop: &mut watch::Receiver<bool>,
) -> Result<bool> {
    if *stop.borrow() {
        return Ok(false);
    }
    tokio::select! {
        biased;
        _ = stop.changed() => Ok(false),
        result = events.send(event) => { result?; Ok(true) }
    }
}

/// A single native scanning session. No GATT pairing or connection is needed.
/// Only actual manufacturer-data events are observations; polling cached
/// PeripheralProperties must never manufacture a new heartbeat.
pub async fn scan_once(
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    stop: watch::Receiver<bool>,
) -> Result<()> {
    scan_with_control(epoch, events, stop, None).await
}

pub async fn scan_with_control(
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    mut stop: watch::Receiver<bool>,
    host: Option<watch::Receiver<HostUpdate>>,
) -> Result<()> {
    let manager = timeout(Duration::from_secs(10), Manager::new())
        .await
        .context("Bluetooth initialization timed out")??;
    let adapters = timeout(Duration::from_secs(5), manager.adapters())
        .await
        .context("adapter enumeration timed out")??;
    let adapter = adapters
        .into_iter()
        .next()
        .context("no Bluetooth LE adapter is available")?;
    let state = timeout(Duration::from_secs(5), adapter.adapter_state())
        .await
        .context("adapter state timed out")??;
    if state != CentralState::PoweredOn {
        bail!("Bluetooth is not ready ({state:?}); check adapter and system permission");
    }
    let mut stream = adapter.events().await?;
    adapter
        .start_scan(ScanFilter {
            services: vec![Uuid::parse_str(SERVICE_UUID)?],
        })
        .await?;
    let (bridge_stop, bridge_stopping) = watch::channel(false);
    let bridge = host.map(|host| {
        tokio::spawn(crate::control::run_bridge(
            adapter.clone(),
            epoch,
            events.clone(),
            host,
            bridge_stopping,
        ))
    });
    let result: Result<()> = async {
        if !emit(&events, TransportEvent::Status { state: TransportState::Scanning, detail: None }, &mut stop).await? { return Ok(()); }
        loop {
            if *stop.borrow() { break; }
            tokio::select! {
                _ = stop.changed() => break,
                event = stream.next() => match event {
                    Some(CentralEvent::ManufacturerDataAdvertisement { id, manufacturer_data }) => {
                        let Some(payload) = manufacturer_data.get(&COMPANY_ID) else { continue; };
                        if !matches!(payload.first(), Some(&2) | Some(&3)) { continue; }
                        let at = epoch.elapsed();
                        let peripheral = adapter.peripheral(&id).await?;
                        let properties = peripheral.properties().await?;
                        let advertisement = RawAdvertisement {
                            received_at: at, address: id.to_string(),
                            name: properties.as_ref().and_then(|properties| properties.local_name.clone()),
                            rssi_dbm: properties.as_ref().and_then(|properties| properties.rssi),
                            payload: payload.clone(),
                        };
                        if !emit(&events, TransportEvent::Advertisement { advertisement }, &mut stop).await? { break; }
                    }
                    Some(CentralEvent::StateUpdate(state)) if state != CentralState::PoweredOn => {
                        bail!("Bluetooth state changed to {state:?}");
                    }
                    None => bail!("native BLE event stream ended"),
                    _ => {}
                }
            }
        }
        Ok(())
    }.await;
    let _ = bridge_stop.send(true);
    if let Some(mut bridge) = bridge
        && timeout(Duration::from_secs(4), &mut bridge).await.is_err()
    {
        bridge.abort();
    }
    let cleanup = timeout(Duration::from_secs(3), adapter.stop_scan()).await;
    result?;
    cleanup.context("stopping BLE scan timed out")??;
    Ok(())
}
