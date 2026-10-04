#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use brelock_core::{
    AppConfig, DeviceId, ProtectionState, ReceiveDisposition,
    control::{ControlGate, ControlRequest, DeviceAction, HostStatus, HostUpdate},
};
use brelock_desktop::{
    backend::{AppSnapshot, Backend, BackendEvent},
    calibration::{CALIBRATION_MIN_SAMPLES, CalibrationReading},
    guided_calibration::{
        CalibrationPoint, GuidedCalibration, GuidedPhase as CalibrationStatus, MultipointResult,
    },
    runtime::stream_control_events,
};
use brelock_platform::{
    ble::{TransportEvent, TransportState},
    storage::ConfigStore,
    system::{
        NativeSessionLocker, SessionLocker, capabilities, open_session_lock_settings,
        prepare_session_lock, reveal_running_application,
    },
};
use serde::Serialize;
use std::{
    collections::VecDeque,
    path::PathBuf,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{
    Emitter, Manager, State,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
};
use tokio::{
    sync::{mpsc, watch},
    time::{MissedTickBehavior, interval, timeout},
};

#[derive(Clone, Serialize)]
struct Sample {
    t_s: f64,
    raw: Option<f64>,
    filtered: Option<f64>,
}
#[derive(Clone, Serialize)]
struct UiEvent {
    id: u64,
    time: u64,
    label: String,
    level: &'static str,
}
#[derive(Clone, Serialize)]
struct ViewState {
    snapshot: AppSnapshot,
    history: Vec<Sample>,
    events: Vec<UiEvent>,
    calibration: CalibrationView,
    config_error: Option<String>,
    control_connected: bool,
    control_error: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
struct CalibrationView {
    status: CalibrationStatus,
    message: String,
    sample_count: usize,
    required_samples: usize,
    progress_percent: u8,
    elapsed_s: f64,
    distance_m: f64,
    step: u8,
    total_steps: u8,
    movement_remaining_s: f64,
    point_progress_percent: u8,
    points: Vec<CalibrationPoint>,
    path_loss_exponent: Option<f64>,
    fit_rmse_db: Option<f64>,
    fit_r_squared: Option<f64>,
    reference_rssi_dbm: Option<f64>,
    margin_db: Option<f64>,
    median_dbm: Option<f64>,
    threshold_dbm: Option<f64>,
    mad_db: Option<f64>,
}

impl Default for CalibrationView {
    fn default() -> Self {
        Self {
            status: CalibrationStatus::Idle,
            message: "Kalibracja w trzech punktach: 1, 2 i 3 m od laptopa.".into(),
            sample_count: 0,
            required_samples: CALIBRATION_MIN_SAMPLES,
            progress_percent: 0,
            elapsed_s: 0.0,
            distance_m: 1.0,
            step: 1,
            total_steps: 3,
            movement_remaining_s: 0.0,
            point_progress_percent: 0,
            points: vec![],
            path_loss_exponent: None,
            fit_rmse_db: None,
            fit_r_squared: None,
            reference_rssi_dbm: None,
            margin_db: None,
            median_dbm: None,
            threshold_dbm: None,
            mad_db: None,
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct LastButtonMarker {
    device_id: DeviceId,
    boot_id: u16,
    count: u8,
}

struct Data {
    backend: Backend,
    history: VecDeque<Sample>,
    events: VecDeque<UiEvent>,
    next_event: u64,
    calibration: CalibrationView,
    calibration_session: Option<GuidedCalibration>,
    last_button_marker: Option<LastButtonMarker>,
    config_error: Option<String>,
    control_gate: ControlGate,
    control_connected: bool,
    control_error: Option<String>,
    control_ack: u16,
    control_feedback: u8,
    control_feedback_at: f64,
}
impl Data {
    fn event(&mut self, label: impl Into<String>, warning: bool) {
        self.next_event += 1;
        self.events.push_back(UiEvent {
            id: self.next_event,
            time: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
            label: label.into(),
            level: if warning { "warning" } else { "info" },
        });
        while self.events.len() > 100 {
            self.events.pop_front();
        }
    }
    fn view(&mut self, epoch: Instant) -> ViewState {
        let now = epoch.elapsed();
        let snapshot = self.backend.snapshot(now);
        ViewState {
            snapshot,
            history: self.history.iter().cloned().collect(),
            events: self.events.iter().cloned().collect(),
            calibration: self.calibration.clone(),
            config_error: self.config_error.clone(),
            control_connected: self.control_connected,
            control_error: self.control_error.clone(),
        }
    }

    fn start_calibration(&mut self, at_s: f64) -> Result<(), String> {
        // A second tap against a slightly delayed host status must not reset an
        // in-progress measurement or send the user back to the start.
        if self.calibration.status.is_active() {
            return Ok(());
        }
        let snapshot = self.backend.snapshot(Duration::from_secs_f64(at_s));
        if snapshot.transport != TransportState::Scanning {
            return Err("Bluetooth nie skanuje. Poczekaj na aktywny odbiór breloka.".into());
        }
        if snapshot.selected.as_ref().is_none_or(|device| {
            device.rssi_filtered_dbm.is_none()
                || device
                    .packet_age_s
                    .is_none_or(|age| age > brelock_core::monitor::RSSI_HOLD_SECONDS)
        }) {
            return Err("Poczekaj na świeży odczyt sygnału z wybranego breloka.".into());
        }
        self.backend.disarm_protection();
        self.control_feedback = 0;
        self.calibration = CalibrationView {
            status: CalibrationStatus::MovingToPoint,
            message: "Odejdź na 1 m od laptopa ustawionego na stole. Potwierdź po odliczaniu."
                .into(),
            movement_remaining_s: 2.0,
            ..CalibrationView::default()
        };
        self.calibration_session = Some(GuidedCalibration::new(at_s));
        self.event(
            "Kalibracja 1 → 2 → 3 m rozpoczęta. Ochrona jest w trybie obserwacji.",
            false,
        );
        Ok(())
    }

    fn cancel_calibration(&mut self) {
        self.calibration = CalibrationView::default();
        self.calibration_session = None;
        self.control_feedback = 0;
        self.event("Kalibracja anulowana. Ochrona pozostaje wyłączona.", false);
    }

    fn observe_button_marker(&mut self, packet: &brelock_core::TelemetryPacket, at_s: f64) {
        if self
            .backend
            .snapshot(Duration::from_secs_f64(at_s))
            .config
            .device_id
            != Some(packet.device_id)
        {
            return;
        }
        let Some(count) = packet.button_event_count else {
            return;
        };
        let marker = LastButtonMarker {
            device_id: packet.device_id,
            boot_id: packet.boot_id,
            count,
        };
        let Some(previous) = self.last_button_marker.replace(marker) else {
            return;
        };
        let new_marker = previous.device_id == marker.device_id
            && previous.boot_id == marker.boot_id
            && previous.count != marker.count
            && packet.button_event_active;
        if !new_marker || !matches!(self.calibration.status, CalibrationStatus::WaitingForMarker) {
            return;
        }

        let _ = self.begin_measurement(at_s);
    }

    fn begin_measurement(&mut self, at_s: f64) -> Result<(), String> {
        if !matches!(self.calibration.status, CalibrationStatus::WaitingForMarker) {
            return Err("Poczekaj na odliczanie i potwierdź pozycję w bieżącym punkcie.".into());
        }
        let snapshot = self.backend.snapshot(Duration::from_secs_f64(at_s));
        if snapshot.transport != TransportState::Scanning
            || snapshot
                .selected
                .is_none_or(|d| !d.telemetry_fresh || d.rssi_filtered_dbm.is_none())
        {
            return Err("Poczekaj na świeże dane Bluetooth z wybranego breloka.".into());
        }
        self.calibration_session
            .as_mut()
            .ok_or("Najpierw rozpocznij serię kalibracji.")?
            .begin_measurement(at_s)
            .map_err(str::to_owned)?;
        self.calibration.status = CalibrationStatus::Collecting;
        self.calibration.message =
            "Pomiar punktu rozpoczęty. Pozostań w miejscu; potem cofniesz się o 1 m.".into();
        self.calibration.point_progress_percent = 0;
        self.calibration.sample_count = 0;
        self.calibration.elapsed_s = 0.0;
        self.control_feedback = 0;
        self.event(
            format!(
                "Kalibracja: zbieram RSSI przy {:.0} m.",
                self.calibration.distance_m
            ),
            false,
        );
        Ok(())
    }

    fn retry_calibration(&mut self, at_s: f64, message: String) {
        if let Some(session) = self.calibration_session.as_mut() {
            session.retry_point(message.clone());
        }
        self.calibration.status = CalibrationStatus::WaitingForMarker;
        self.calibration.message = message;
        self.control_feedback = 4;
        self.control_feedback_at = at_s;
        self.event(self.calibration.message.clone(), true);
    }

    fn restart_calibration(&mut self, at_s: f64, message: String) {
        if let Some(session) = self.calibration_session.as_mut() {
            session.restart(at_s, message.clone());
        }
        self.calibration = CalibrationView {
            status: CalibrationStatus::MovingToPoint,
            movement_remaining_s: 2.0,
            message: message.clone(),
            ..CalibrationView::default()
        };
        self.event(message, true);
    }

    fn advance_calibration(&mut self, at_s: f64, config_path: &std::path::Path) {
        let Some(session) = self.calibration_session.as_mut() else {
            return;
        };
        let progress = session.poll(at_s);
        self.calibration.status = progress.phase;
        self.calibration.step = progress.step;
        self.calibration.distance_m = progress.distance_m;
        self.calibration.movement_remaining_s = progress.movement_remaining_s;
        self.calibration.point_progress_percent = progress.point_percent;
        self.calibration.points = progress.points;
        self.calibration.sample_count = progress.sample_count;
        self.calibration.progress_percent = progress.percent;
        self.calibration.elapsed_s = progress.elapsed_s;
        self.calibration.message = progress.message;
        if let Some(notice) = progress.notice {
            self.event(notice, true);
        }
        if let Some(result) = progress.result
            && let Err(error) = self.apply_calibration(result, at_s, config_path)
        {
            let message = format!(
                "Seria gotowa, ale zapis się nie powiódł: {error}. Poprzednie ustawienia zachowano. Powtórz serię od 1 m."
            );
            self.restart_calibration(at_s, message);
        }
    }

    fn apply_calibration(
        &mut self,
        result: MultipointResult,
        at_s: f64,
        config_path: &std::path::Path,
    ) -> Result<(), String> {
        let current = self.backend.snapshot(Duration::from_secs_f64(at_s)).config;
        let config = result
            .calibrated_config(&current)
            .map_err(|error| error.to_string())?;
        let reference_rssi_dbm = config.reference_rssi_dbm;
        let n = config.path_loss_exponent;
        ConfigStore::save(config_path, &config).map_err(|error| format!("{error:#}"))?;
        self.backend
            .configure(config)
            .map_err(|error| format!("{error:#}"))?;
        self.calibration.status = CalibrationStatus::Complete;
        self.calibration.message = format!(
            "Seria 1, 2 i 3 m zapisana. Dopasowano RSSI odniesienia i n = {n:.2}. Ochronę włączysz osobno."
        );
        let boundary = result
            .points
            .last()
            .ok_or("Brak ostatniego punktu kalibracji.")?
            .result;
        self.calibration.sample_count = result.points.iter().map(|p| p.result.sample_count).sum();
        self.calibration.median_dbm = Some(boundary.median_dbm);
        self.calibration.threshold_dbm = Some(boundary.threshold_dbm);
        self.calibration.mad_db = Some(boundary.mad_db);
        self.calibration.margin_db = Some(boundary.margin_db);
        self.calibration.path_loss_exponent = Some(n);
        self.calibration.fit_rmse_db = Some(result.rmse_db);
        self.calibration.fit_r_squared = Some(result.r_squared);
        self.calibration.reference_rssi_dbm = Some(reference_rssi_dbm);
        self.calibration.progress_percent = 100;
        self.calibration.point_progress_percent = 100;
        self.calibration_session = None;
        self.control_feedback = 3;
        self.control_feedback_at = at_s;
        self.event(
            format!(
                "Kalibracja 1/2/3 m: próg {:.1} dBm, RSSI odniesienia {:.1} dBm, n {:.2}, RMSE {:.2} dB.",
                boundary.threshold_dbm, reference_rssi_dbm,n,result.rmse_db
            ),
            false,
        );
        Ok(())
    }

    fn host_update(&mut self, at_s: f64) -> HostUpdate {
        let snapshot = self.backend.snapshot(Duration::from_secs_f64(at_s));
        let device = snapshot.selected.as_ref();
        let fresh = device.is_some_and(|d| d.telemetry_fresh && d.rssi_filtered_dbm.is_some());
        let waiting = matches!(self.calibration.status, CalibrationStatus::WaitingForMarker);
        let percent = self.calibration.point_progress_percent;
        HostUpdate {
            device_id: snapshot.config.device_id,
            status: HostStatus {
                protection: match snapshot.protection.state {
                    ProtectionState::Disabled => 0,
                    ProtectionState::Armed => 1,
                    ProtectionState::Tripped => 2,
                },
                flags: u8::from(fresh)
                    | (u8::from(snapshot.capabilities.session_lock) << 1)
                    | (u8::from(snapshot.config.departure_threshold_dbm.is_some()) << 2),
                calibration: if matches!(self.calibration.status, CalibrationStatus::MovingToPoint)
                {
                    5
                } else if waiting && self.control_feedback == 4 {
                    3
                } else if matches!(self.calibration.status, CalibrationStatus::Collecting) {
                    4
                } else if waiting {
                    1
                } else if matches!(self.calibration.status, CalibrationStatus::Complete) {
                    2
                } else {
                    0
                },
                feedback: if at_s - self.control_feedback_at <= 5.0 {
                    self.control_feedback
                } else {
                    0
                },
                calibration_percent: percent,
                calibration_step: if self.calibration.status.is_active()
                    || matches!(self.calibration.status, CalibrationStatus::Complete)
                {
                    self.calibration.step
                } else {
                    0
                },
                movement_seconds: self.calibration.movement_remaining_s.ceil().clamp(0.0, 2.0)
                    as u8,
                rssi_dbm: fresh
                    .then(|| {
                        device
                            .and_then(|d| d.rssi_filtered_dbm)
                            .map(|rssi| rssi.round().clamp(-127.0, 20.0) as i8)
                    })
                    .flatten(),
                distance_cm: fresh
                    .then(|| {
                        device
                            .and_then(|d| d.distance_estimate_m)
                            .filter(|m| m.is_finite() && *m >= 0.0 && *m < 655.35)
                            .map(|m| (m * 100.0).round() as u16)
                    })
                    .flatten(),
                acknowledged_sequence: self.control_ack,
                session: self.control_gate.session,
            },
        }
    }

    fn reset_control_session(&mut self) {
        self.control_gate = ControlGate::new(uuid::Uuid::new_v4().as_u64_pair().0);
        self.control_ack = 0;
        self.control_feedback = 0;
    }

    fn control_request(&mut self, id: DeviceId, request: ControlRequest, at_s: f64) -> bool {
        let snapshot = self.backend.snapshot(Duration::from_secs_f64(at_s));
        if snapshot.config.device_id != Some(id)
            || !self.control_connected
            || !self.control_gate.accept(request)
        {
            return false;
        }
        self.control_ack = request.sequence;
        self.control_feedback = 0;
        self.control_feedback_at = at_s;
        match request.action {
            DeviceAction::StartCalibration => {
                if let Err(error) = self.start_calibration(at_s) {
                    self.control_feedback = 4;
                    self.event(error, true);
                }
            }
            DeviceAction::SaveCalibration => {
                if matches!(self.calibration.status, CalibrationStatus::WaitingForMarker) {
                    if let Err(error) = self.begin_measurement(at_s) {
                        self.control_feedback = 4;
                        self.event(error, true);
                    }
                } else if !matches!(self.calibration.status, CalibrationStatus::Collecting) {
                    self.control_feedback = 4;
                    self.event(
                        "Najpierw rozpocznij kalibrację na breloku lub w aplikacji.",
                        true,
                    );
                }
            }
            DeviceAction::CancelCalibration => self.cancel_calibration(),
            DeviceAction::LockNow => {
                if !snapshot.capabilities.session_lock
                    || snapshot.selected.is_none_or(|d| !d.telemetry_fresh)
                {
                    self.control_feedback = 2;
                    self.event(
                        "Zdalna blokada niedostępna: brak uprawnienia lub świeżego połączenia.",
                        true,
                    );
                } else {
                    return true;
                }
            }
        }
        false
    }
}
struct Desktop {
    data: Mutex<Data>,
    epoch: Instant,
    config_path: PathBuf,
    stop: watch::Sender<bool>,
    done: watch::Receiver<bool>,
    quitting: AtomicBool,
}

#[tauri::command]
fn get_state(state: State<'_, Arc<Desktop>>) -> Result<ViewState, String> {
    Ok(state
        .data
        .lock()
        .map_err(|_| "Backend jest niedostępny.")?
        .view(state.epoch))
}

fn replace_config(state: &Desktop, config: AppConfig) -> Result<(), String> {
    config.validate().map_err(|error| error.to_string())?;
    let mut data = state.data.lock().map_err(|_| "Backend jest niedostępny.")?;
    let same_device = data
        .backend
        .snapshot(state.epoch.elapsed())
        .config
        .device_id
        == config.device_id;
    ConfigStore::save(&state.config_path, &config)
        .map_err(|error| format!("Nie udało się zapisać ustawień: {error:#}"))?;
    data.backend
        .configure(config)
        .map_err(|error| error.to_string())?;
    if data.calibration.status.is_active() {
        data.event("Kalibracja przerwana przez zmianę ustawień.", true);
    }
    data.calibration = CalibrationView::default();
    data.calibration_session = None;
    data.last_button_marker = None;
    data.history.clear();
    data.reset_control_session();
    if !same_device {
        data.control_connected = false;
        data.control_error = None;
    }
    data.config_error = None;
    data.event("Ustawienia zapisane. Tryb obserwacji.", false);
    Ok(())
}

#[tauri::command]
fn save_config(config: AppConfig, state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    replace_config(&state, config)
}

#[tauri::command]
fn start_distance_calibration(state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|_| "Backend jest niedostępny.")?;
    data.start_calibration(state.epoch.elapsed().as_secs_f64())
}

#[tauri::command]
fn capture_distance_calibration(state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|_| "Backend jest niedostępny.")?;
    if !matches!(data.calibration.status, CalibrationStatus::WaitingForMarker) {
        return Err("Najpierw rozpocznij kalibrację.".into());
    }
    data.begin_measurement(state.epoch.elapsed().as_secs_f64())
}

#[tauri::command]
fn cancel_distance_calibration(state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    let mut data = state.data.lock().map_err(|_| "Backend jest niedostępny.")?;
    data.cancel_calibration();
    Ok(())
}
#[tauri::command]
fn select_device(device_id: String, state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    let id: DeviceId = device_id
        .parse()
        .map_err(|error| format!("Niepoprawny ID: {error}"))?;
    let mut config = state
        .data
        .lock()
        .map_err(|_| "Backend jest niedostępny.")?
        .view(state.epoch)
        .snapshot
        .config;
    if config.device_id != Some(id) {
        config.departure_threshold_dbm = None;
    }
    config.device_id = Some(id);
    replace_config(&state, config)
}
#[tauri::command]
fn set_protection(enabled: bool, state: State<'_, Arc<Desktop>>) -> Result<(), String> {
    if enabled {
        prepare_session_lock().map_err(|error| format!("{error:#}"))?;
    }
    let mut data = state.data.lock().map_err(|_| "Backend jest niedostępny.")?;
    if enabled {
        if data.calibration.status.is_active() {
            return Err("Zakończ lub anuluj kalibrację przed uzbrojeniem ochrony.".into());
        }
        if !capabilities().session_lock {
            return Err(if cfg!(target_os = "macos") {
                "Aby uzbroić ochronę, włącz breLock w Ustawienia systemowe → Prywatność i ochrona → Dostępność, a potem uruchom aplikację ponownie.".into()
            } else {
                "Blokada sesji nie jest dostępna na tym systemie.".into()
            });
        }
        data.backend
            .arm_protection(state.epoch.elapsed())
            .map_err(str::to_owned)?;
        data.event("Ochrona uzbrojona. Analizuję świeże dane breloka.", false);
    } else {
        data.backend.disarm_protection();
        data.event("Ochrona wyłączona.", false);
    }
    Ok(())
}
#[tauri::command]
fn hide_window(app: tauri::AppHandle) -> Result<(), String> {
    if app.tray_by_id("main").is_none() {
        return Err("Ikona na pasku jest niedostępna. Okno pozostaje otwarte.".into());
    }
    app.get_webview_window("main")
        .ok_or("Brak okna.")?
        .hide()
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn open_protection_settings() -> Result<(), String> {
    open_session_lock_settings().map_err(|error| format!("{error:#}"))
}

#[tauri::command]
fn show_running_application() -> Result<(), String> {
    reveal_running_application().map_err(|error| format!("{error:#}"))
}
fn show_window(app: &tauri::AppHandle, tab: Option<&str>) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
        if let Some(tab) = tab {
            let _ = window.emit("brelock:navigate", tab);
        }
    }
}
fn request_quit(app: &tauri::AppHandle) {
    let state = app.state::<Arc<Desktop>>();
    if state.quitting.swap(true, Ordering::SeqCst) {
        return;
    }
    let _ = state.stop.send(true);
    let mut done = state.done.clone();
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let _ = timeout(Duration::from_secs(6), async {
            if !*done.borrow() {
                let _ = done.changed().await;
            }
        })
        .await;
        app.exit(0);
    });
}

fn run_backend(
    app: tauri::AppHandle,
    state: Arc<Desktop>,
    mut stopping: watch::Receiver<bool>,
    finished: watch::Sender<bool>,
) {
    tauri::async_runtime::spawn(async move {
        let (events, mut incoming) = mpsc::channel(256);
        let initial = state
            .data
            .lock()
            .unwrap()
            .host_update(state.epoch.elapsed().as_secs_f64());
        let (host_status, host_updates) = watch::channel(initial);
        let mut source = tokio::spawn(stream_control_events(
            state.epoch,
            events,
            stopping.clone(),
            host_updates,
        ));
        let mut timer = interval(Duration::from_millis(200));
        timer.set_missed_tick_behavior(MissedTickBehavior::Skip);
        loop {
            tokio::select! {
                biased;
                _ = stopping.changed() => break,
                event = incoming.recv() => {
                    let Some(event) = event else { break; };
                    let observed_rssi = match &event {
                        TransportEvent::Advertisement { advertisement } => advertisement.rssi_dbm
                            .filter(|rssi| (-127..=-1).contains(rssi)).map(f64::from),
                        _ => None,
                    };
                    let mut remote_lock = false;
                    if let Ok(mut data) = state.data.lock() {
                        if let TransportEvent::ControlLink { device_id, connected, detail } = &event
                            && data.backend.snapshot(state.epoch.elapsed()).config.device_id == Some(*device_id) {
                            if data.control_connected != *connected {
                                data.event(if *connected { "Brelok połączony: ekran i zdalne akcje aktywne." }
                                    else { "Kanał sterowania breloka rozłączony." }, !*connected);
                            }
                            data.control_connected = *connected;
                            data.control_error = detail.clone();
                            if !connected {
                                if data.calibration.status.is_active() {
                                    data.retry_calibration(state.epoch.elapsed().as_secs_f64(), "Połączenie BLE przerwane. Po połączeniu potwierdź POMIAR ponownie w bieżącym punkcie; poprzednie ustawienia zachowano.".into());
                                }
                                // The fob resets its command counter after a
                                // reconnect/reboot. Give the next link a fresh
                                // nonce, so sequence 1 works and old commands
                                // cannot be replayed into that connection.
                                data.reset_control_session();
                            }
                        }
                        if let TransportEvent::Control { device_id, request } = &event {
                            remote_lock = data.control_request(*device_id, *request,
                                state.epoch.elapsed().as_secs_f64());
                        }
                        if let TransportEvent::Status { state: transport, detail } = &event {
                            let previous = data.view(state.epoch).snapshot.transport;
                            if previous != *transport && matches!(transport, TransportState::Unavailable | TransportState::Scanning) {
                                data.event(if *transport == TransportState::Scanning { "Skanowanie BLE działa.".into() } else { format!("Bluetooth niedostępny: {}", detail.as_deref().unwrap_or("brak adaptera")) }, *transport == TransportState::Unavailable);
                            }
                        }
                        match data.backend.transport_event(event) {
                            Ok(Some(BackendEvent::Packet { t_s, telemetry, disposition, .. })) => {
                                if matches!(disposition, ReceiveDisposition::Reboot)
                                    && data.calibration_session.is_some() {
                                    data.restart_calibration(t_s,"Brelok uruchomił się ponownie. Powtórz serię od 1 m; poprzednie ustawienia zachowano.".into());
                                }
                                if let Some(rssi) = observed_rssi && matches!(disposition,
                                    ReceiveDisposition::New | ReceiveDisposition::Reboot | ReceiveDisposition::Duplicate)
                                    && let Some(device) = data.backend.snapshot(Duration::from_secs_f64(t_s)).selected
                                    && device.device_id == telemetry.device_id && device.telemetry_fresh
                                    && let Some(session) = data.calibration_session.as_mut() {
                                        session.observe(CalibrationReading { t_s, rssi_dbm: rssi });
                                }
                                if matches!(disposition, ReceiveDisposition::New | ReceiveDisposition::Reboot | ReceiveDisposition::Duplicate) {
                                    data.observe_button_marker(&telemetry, t_s);
                                }
                            }
                            Ok(_) => {}
                            Err(error) => data.event(error.to_string(), true),
                        }
                    }
                    if remote_lock {
                        let outcome = prepare_session_lock()
                            .and_then(|()| NativeSessionLocker.lock_session());
                        if let Ok(mut data) = state.data.lock() {
                            data.control_feedback_at = state.epoch.elapsed().as_secs_f64();
                            match outcome {
                                Ok(()) => {
                                    data.control_feedback = 1;
                                    data.event("Brelok: żądanie ręcznej blokady systemu wysłane.", false);
                                }
                                Err(error) => {
                                    data.control_feedback = 2;
                                    data.event(format!("Brelok: blokada odrzucona: {error:#}"), true);
                                }
                            }
                        }
                    }
                }
                _ = timer.tick() => {
                    let decision = if let Ok(mut data) = state.data.lock() {
                        data.advance_calibration(state.epoch.elapsed().as_secs_f64(), &state.config_path);
                        let (snapshot, reason, auto_rearmed) = data.backend.tick(state.epoch.elapsed());
                        if auto_rearmed {
                            data.event("Brelok wrócił do komputera. Ochrona uzbroiła się ponownie.", false);
                        }
                        let sample = Sample { t_s: snapshot.t_s, raw: snapshot.selected.as_ref().and_then(|d| d.rssi_raw_dbm), filtered: snapshot.selected.as_ref().and_then(|d| d.rssi_filtered_dbm) };
                        data.history.push_back(sample);
                        while data.history.len() > 301 || data.history.front().is_some_and(|s| s.t_s < snapshot.t_s - 60.0) { data.history.pop_front(); }
                        reason
                    } else { None };
                    if let Some(reason) = decision {
                        // Keep OS calls outside the backend mutex. The engine has
                        // already latched this episode, so this is the only attempt.
                        let outcome = NativeSessionLocker.lock_session();
                        if let Ok(mut data) = state.data.lock() {
                            match outcome {
                                Ok(()) => {
                                    data.backend.record_lock_attempt(Ok(()));
                                    data.event(format!("{}: {}. Żądanie blokady systemu wysłane.", reason.code(), reason.label()), false);
                                }
                                Err(error) => {
                                    let message = format!("{}: {}. Nie udało się zablokować komputera: {error:#}", reason.code(), reason.label());
                                    data.backend.record_lock_attempt(Err(format!("{error:#}")));
                                    data.event(message, true);
                                }
                            }
                        }
                    }
                    let view = state.data.lock().ok().map(|mut data| data.view(state.epoch));
                    if let Ok(mut data) = state.data.lock() {
                        host_status.send_replace(data.host_update(state.epoch.elapsed().as_secs_f64()));
                    }
                    if let (Some(view), Some(window)) = (view, app.get_webview_window("main"))
                        && window.is_visible().unwrap_or(false) {
                        let _ = window.emit("brelock:state", view);
                    }
                }
            }
        }
        incoming.close();
        if timeout(Duration::from_secs(5), &mut source).await.is_err() {
            source.abort();
            let _ = source.await;
        }
        let _ = finished.send(true);
    });
}

fn tray_icon() -> tauri::image::Image<'static> {
    // Native monochrome shield; transparent background for the macOS menu bar.
    let mut rgba = vec![0u8; 32 * 32 * 4];
    for y in 0..32usize {
        for x in 0..32usize {
            let xf = x as f64;
            let yf = y as f64;
            let edge = if (5.0..=11.0).contains(&yf) {
                (yf - (5.0 + (xf - 15.5).abs() * 0.37)).abs() < 1.3
            } else if (10.0..=20.0).contains(&yf) {
                (xf - 6.0).abs() < 1.2 || (xf - 25.0).abs() < 1.2
            } else if (20.0..=29.0).contains(&yf) {
                (yf - (29.0 - (xf - 15.5).abs() * 0.95)).abs() < 1.3
            } else {
                false
            };
            if edge {
                let i = (y * 32 + x) * 4;
                rgba[i..i + 4].copy_from_slice(&[180, 201, 232, 255]);
            }
        }
    }
    tauri::image::Image::new_owned(rgba, 32, 32)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            show_window(app, None)
        }))
        .invoke_handler(tauri::generate_handler![
            get_state,
            select_device,
            save_config,
            set_protection,
            start_distance_calibration,
            capture_distance_calibration,
            cancel_distance_calibration,
            hide_window,
            open_protection_settings,
            show_running_application
        ])
        .setup(|app| {
            let config_path = std::env::var_os("BRELOCK_CONFIG_PATH")
                .map(PathBuf::from)
                .map_or_else(ConfigStore::default_path, Ok)?;
            let (config, config_error) = if config_path.exists() {
                match ConfigStore::load(&config_path) {
                    Ok(config) => (config, None),
                    Err(error) => (AppConfig::default(), Some(format!("{error:#}"))),
                }
            } else {
                (AppConfig::default(), None)
            };
            let mut data = Data {
                backend: Backend::new(config)?,
                history: VecDeque::new(),
                events: VecDeque::new(),
                next_event: 0,
                calibration: CalibrationView::default(),
                calibration_session: None,
                last_button_marker: None,
                config_error,
                control_gate: ControlGate::new(uuid::Uuid::new_v4().as_u64_pair().0),
                control_connected: false,
                control_error: None,
                control_ack: 0,
                control_feedback: 0,
                control_feedback_at: 0.0,
            };
            data.event("Aplikacja działa w tle. Ochrona wyłączona.", false);
            let (stop, stopping) = watch::channel(false);
            let (finished, done) = watch::channel(false);
            let state = Arc::new(Desktop {
                data: Mutex::new(data),
                epoch: Instant::now(),
                config_path,
                stop,
                done,
                quitting: AtomicBool::new(false),
            });
            app.manage(state.clone());
            let status = MenuItem::with_id(
                app,
                "status",
                "breLock · Status w oknie",
                false,
                None::<&str>,
            )?;
            let open = MenuItem::with_id(app, "open", "Otwórz breLock", true, None::<&str>)?;
            let diagnostic =
                MenuItem::with_id(app, "diagnostic", "Diagnostyka", true, None::<&str>)?;
            let settings = MenuItem::with_id(app, "settings", "Ustawienia", true, None::<&str>)?;
            let separator = PredefinedMenuItem::separator(app)?;
            let quit = MenuItem::with_id(app, "quit", "Zakończ breLock", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[&status, &open, &diagnostic, &settings, &separator, &quit],
            )?;
            let tray = TrayIconBuilder::with_id("main")
                .icon(tray_icon())
                .icon_as_template(true)
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => show_window(app, Some("status")),
                    "diagnostic" => show_window(app, Some("diagnostics")),
                    "settings" => show_window(app, Some("settings")),
                    "quit" => request_quit(app),
                    _ => {}
                });
            #[cfg(target_os = "windows")]
            let tray = tray
                .show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| {
                    if matches!(
                        event,
                        tauri::tray::TrayIconEvent::Click {
                            button: tauri::tray::MouseButton::Left,
                            button_state: tauri::tray::MouseButtonState::Up,
                            ..
                        }
                    ) {
                        show_window(tray.app_handle(), None);
                    }
                });
            let tray = tray.build(app);
            let background = std::env::args().any(|arg| arg == "--background") && tray.is_ok();
            if let Err(error) = tray
                && let Ok(mut data) = state.data.lock()
            {
                data.event(format!("Nie udało się utworzyć ikony: {error}"), true);
            }
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            if !background {
                show_window(app.handle(), None);
            }
            run_backend(app.handle().clone(), state, stopping, finished);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event
                && window.app_handle().tray_by_id("main").is_some()
            {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("Nie udało się uruchomić breLock.")
        .run(|app, event| match event {
            tauri::RunEvent::ExitRequested { api, .. } => {
                let state = app.state::<Arc<Desktop>>();
                if !state.quitting.load(Ordering::SeqCst) {
                    api.prevent_exit();
                    request_quit(app);
                }
            }
            #[cfg(target_os = "macos")]
            tauri::RunEvent::Reopen { .. } => show_window(app, None),
            _ => {}
        });
}
