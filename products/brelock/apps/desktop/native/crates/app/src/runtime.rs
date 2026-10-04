use crate::backend::Backend;
use anyhow::{Context, Result, bail};
use brelock_core::{AppConfig, control::HostUpdate};
use brelock_platform::{
    ble::{RawAdvertisement, TransportEvent, TransportState, scan_with_control},
    storage::JsonlTrace,
};
use serde::Serialize;
use serde_json::json;
use std::{
    future::pending,
    io::{self, Write},
    path::PathBuf,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tokio::{
    sync::{mpsc, watch},
    time::{MissedTickBehavior, interval, sleep, timeout},
};

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Ble,
    Demo,
}

pub struct RunOptions {
    pub source: Source,
    pub duration: Option<Duration>,
    pub log: Option<PathBuf>,
}

/// Shared transport used by the console and the desktop host. Its lifetime is
/// controlled by Rust, independently of any window or frontend subscriber.
pub async fn stream_events(
    source: Source,
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    stop: watch::Receiver<bool>,
) -> Result<()> {
    match source {
        Source::Ble => ble_source(epoch, events, stop, None).await,
        Source::Demo => demo_source(epoch, events, stop).await,
    }
}

pub async fn stream_control_events(
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    stop: watch::Receiver<bool>,
    host: watch::Receiver<HostUpdate>,
) -> Result<()> {
    ble_source(epoch, events, stop, Some(host)).await
}

fn record(event: &impl Serialize, trace: &mut Option<JsonlTrace>, stdout: bool) -> Result<()> {
    if let Some(trace) = trace {
        trace.record(event)?;
    }
    if stdout {
        let mut output = io::stdout().lock();
        serde_json::to_writer(&mut output, event)?;
        writeln!(output)?;
        output.flush()?;
    }
    Ok(())
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

async fn ble_source(
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    mut stop: watch::Receiver<bool>,
    host: Option<watch::Receiver<HostUpdate>>,
) -> Result<()> {
    let mut attempt = 0u32;
    while !*stop.borrow() {
        if !emit(
            &events,
            TransportEvent::Status {
                state: TransportState::Starting,
                detail: None,
            },
            &mut stop,
        )
        .await?
        {
            break;
        }
        match scan_with_control(epoch, events.clone(), stop.clone(), host.clone()).await {
            Ok(()) => break,
            Err(error) => {
                attempt = attempt.saturating_add(1);
                if !emit(
                    &events,
                    TransportEvent::Status {
                        state: TransportState::Unavailable,
                        detail: Some(format!("{error:#}")),
                    },
                    &mut stop,
                )
                .await?
                {
                    break;
                }
                tokio::select! {
                    _ = stop.changed() => break,
                    _ = sleep(Duration::from_secs_f64((0.5 * 2.0_f64.powi(attempt.min(5) as i32 - 1)).min(5.0))) => {}
                }
            }
        }
    }
    Ok(())
}

async fn demo_source(
    epoch: Instant,
    events: mpsc::Sender<TransportEvent>,
    mut stop: watch::Receiver<bool>,
) -> Result<()> {
    emit(
        &events,
        TransportEvent::Status {
            state: TransportState::Demo,
            detail: None,
        },
        &mut stop,
    )
    .await?;
    let mut sequence = 0u32;
    let mut timer = interval(Duration::from_millis(200));
    timer.set_missed_tick_behavior(MissedTickBehavior::Skip);
    loop {
        tokio::select! {
            _ = stop.changed() => break,
            _ = timer.tick() => {
                let phase = epoch.elapsed().as_secs_f64() % 32.0;
                let current_sequence = sequence;
                sequence = sequence.wrapping_add(1);
                if (14.0..22.0).contains(&phase) { continue; }
                let moving = phase >= 5.0;
                let baseline = if phase < 5.0 { -56.0 } else if phase < 14.0 { -56.0 - 2.0 * (phase - 5.0) } else { -74.0 + 1.8 * (phase - 22.0) };
                let mut payload = vec![0u8; 24];
                payload[0] = 2;
                payload[1] = 1;
                payload[2..8].copy_from_slice(&[0xa1, 0xb2, 0xc3, 0xd4, 0xe5, 0xf6]);
                payload[8..10].copy_from_slice(&0x1234u16.to_le_bytes());
                payload[10..14].copy_from_slice(&current_sequence.to_le_bytes());
                payload[14] = if moving { 0x17 } else { 0x16 };
                payload[15..17].copy_from_slice(&(if moving { 140u16 } else { 12 }).to_le_bytes());
                payload[17..19].copy_from_slice(&(if moving { 240u16 } else { 8 }).to_le_bytes());
                payload[19..21].copy_from_slice(&(if moving { 0u16 } else { 65535 }).to_le_bytes());
                payload[21..23].copy_from_slice(&3980u16.to_le_bytes());
                payload[23] = 3;
                let advertisement = RawAdvertisement { received_at: epoch.elapsed(), address: "DEMO".into(), name: Some("breLock synthetic".into()),
                    rssi_dbm: Some((baseline + (f64::from(current_sequence) * 0.7).sin()).round() as i16), payload };
                if !emit(&events, TransportEvent::Advertisement { advertisement: advertisement.clone() }, &mut stop).await? { break; }
                if current_sequence.is_multiple_of(3) && !emit(&events, TransportEvent::Advertisement { advertisement }, &mut stop).await? { break; }
            }
        }
    }
    Ok(())
}

async fn duration_expired(duration: Option<Duration>) {
    match duration {
        Some(duration) => sleep(duration).await,
        None => pending::<()>().await,
    }
}

/// Compose the application lifetime. This console entry point only serializes
/// snapshots; a future native shell can consume Backend without this writer.
pub async fn run(config: AppConfig, options: RunOptions) -> Result<()> {
    let mut backend = Backend::new(config.clone())?;
    let mut trace = options.log.as_deref().map(JsonlTrace::create).transpose()?;
    let epoch = Instant::now();
    record(
        &json!({"type": "session", "source": options.source, "mode": "observe", "config": config,
        "started_unix_s": SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs_f64()}),
        &mut trace,
        true,
    )?;
    let (events, mut incoming) = mpsc::channel(256);
    let (stop, stopping) = watch::channel(false);
    let mut worker = tokio::spawn(async move {
        match options.source {
            Source::Ble => ble_source(epoch, events, stopping, None).await,
            Source::Demo => demo_source(epoch, events, stopping).await,
        }
    });
    let mut timer = interval(Duration::from_secs_f64(1.0 / config.refresh_hz));
    timer.set_missed_tick_behavior(MissedTickBehavior::Skip);
    let deadline = duration_expired(options.duration);
    tokio::pin!(deadline);
    let result: Result<&str> = async {
        loop {
            tokio::select! {
                biased;
                result = tokio::signal::ctrl_c() => { result?; break Ok("interrupt"); }
                _ = &mut deadline => break Ok("duration"),
                _ = timer.tick() => {
                    let snapshot = backend.snapshot(epoch.elapsed());
                    record(&json!({"type": "snapshot", "snapshot": snapshot}), &mut trace, true)?;
                }
                event = incoming.recv() => {
                    let event = event.context("transport task ended unexpectedly")?;
                    record(&event, &mut trace, false)?;
                    if let Some(event) = backend.transport_event(event)? { record(&event, &mut trace, false)?; }
                }
            }
        }
    }.await;
    let _ = stop.send(true);
    // Keep the receiver alive during graceful shutdown, but do not let a full
    // channel hold the source task waiting to enqueue more observations.
    incoming.close();
    let cleanup = match timeout(Duration::from_secs(5), &mut worker).await {
        Ok(outcome) => outcome
            .context("transport task panicked")
            .and_then(|result| result),
        Err(_) => {
            worker.abort();
            let _ = worker.await;
            Ok(())
        }
    };
    let reason = result?;
    cleanup?;
    let snapshot = backend.snapshot(epoch.elapsed());
    record(
        &json!({"type": "end", "reason": reason, "snapshot": snapshot}),
        &mut trace,
        true,
    )?;
    if matches!(options.source, Source::Ble) {
        if matches!(
            snapshot.transport,
            TransportState::Starting | TransportState::Unavailable
        ) {
            bail!(
                "BLE unavailable: {}",
                snapshot
                    .last_error
                    .as_deref()
                    .unwrap_or("initialization did not finish")
            );
        }
        if snapshot.config.device_id.is_some()
            && snapshot
                .selected
                .as_ref()
                .is_none_or(|device| device.last_packet.is_none())
        {
            bail!("the selected keyfob was not received during this session");
        }
    }
    Ok(())
}
