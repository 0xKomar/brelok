//! Observe calibration on real GATT/RSSI without changing settings or locking OS.
use anyhow::{Context, Result};
use brelock_core::{
    DeviceId,
    control::{HostStatus, HostUpdate},
    decode_telemetry,
};
use brelock_desktop::{
    calibration::{CalibrationMeasurement, CalibrationReading},
    runtime::stream_control_events,
};
use brelock_platform::ble::TransportEvent;
use std::{
    fs::File,
    io::Write,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tokio::{
    sync::{mpsc, watch},
    time::{interval, timeout},
};

#[tokio::main]
async fn main() -> Result<()> {
    let mut arguments = std::env::args().skip(1);
    let id: DeviceId = arguments
        .next()
        .context("usage: calibration_probe DEVICE_ID NEW_TRACE.jsonl")?
        .parse()?;
    let trace_path = arguments.next().context("missing trace path")?;
    let mut trace = File::options()
        .write(true)
        .create_new(true)
        .open(trace_path)?;
    let epoch = Instant::now();
    let session = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;
    let update = HostUpdate {
        device_id: Some(id),
        status: HostStatus {
            session,
            ..Default::default()
        },
    };
    let (host, updates) = watch::channel(update);
    let (stop, stopping) = watch::channel(false);
    let (sender, mut events) = mpsc::channel(256);
    let mut source = tokio::spawn(stream_control_events(epoch, sender, stopping, updates));
    let mut measurement = None;
    let mut timer = interval(Duration::from_millis(200));
    let outcome: Result<()> = async {
        loop {
            tokio::select! {
                event = events.recv() => {
                    let event = event.context("BLE source stopped")?;
                    serde_json::to_writer(&mut trace, &event)?;
                    writeln!(trace)?;
                    match event {
                        TransportEvent::ControlLink { device_id, connected: true, .. } if device_id == id => {
                            measurement = Some(CalibrationMeasurement::new(epoch.elapsed().as_secs_f64()));
                            println!("GATT connected; measuring real RSSI at current position (no settings saved).");
                        }
                        TransportEvent::ControlLink { connected: false, detail, .. } if measurement.is_some() => {
                            anyhow::bail!("GATT disconnected during measurement: {detail:?}");
                        }
                        TransportEvent::Advertisement { advertisement } => {
                            if decode_telemetry(&advertisement.payload)?.device_id == id
                                && let Some(rssi) = advertisement.rssi_dbm
                                && let Some(run) = measurement.as_mut() {
                                run.observe(CalibrationReading { t_s: advertisement.received_at.as_secs_f64(), rssi_dbm: f64::from(rssi) });
                            }
                        }
                        _ => {}
                    }
                }
                _ = timer.tick() => {
                    let now_s = epoch.elapsed().as_secs_f64();
                    if now_s >= 50.0 { anyhow::bail!("No successful measurement within 50 s"); }
                    if let Some(run) = measurement.as_mut() {
                        let progress = run.poll(now_s);
                        host.send_replace(HostUpdate { status: HostStatus { calibration: 4, calibration_percent: progress.percent, ..update.status }, ..update });
                        if let Some(result) = progress.result {
                            println!("PASS real RSSI: {} samples, {:.1}s, median {:.1}dBm, MAD {:.1}dB, margin {:.1}dB, candidate threshold {:.1}dBm. Settings unchanged.", result.sample_count, progress.elapsed_s, result.median_dbm, result.mad_db, result.margin_db, result.threshold_dbm);
                            break;
                        }
                        if progress.timed_out { anyhow::bail!("Calibration timed out: {} ({} samples)", progress.message, progress.sample_count); }
                    }
                }
            }
        }
        Ok(())
    }.await;
    host.send_replace(update);
    stop.send_replace(true);
    if timeout(Duration::from_secs(5), &mut source).await.is_err() {
        source.abort();
    }
    outcome
}
