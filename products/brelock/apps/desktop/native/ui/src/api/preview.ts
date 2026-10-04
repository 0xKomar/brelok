import type { Config, Device, Driver, Event, Snapshot, ViewState } from './types';
import { appendSample, defaultConfig } from '../state/presentation';

// Browser-only design preview. Every visible screen is marked DEMO.
export class PreviewDriver implements Driver {
  readonly preview = true;
  private config: Config = { ...defaultConfig(), device_id: 'A1B2C3D4E5F6' };
  private sequence = 0;
  private history: ViewState['history'] = [];
  private events: Event[] = [];
  private calibration: ViewState['calibration'] = {
    status: 'idle', message: 'Wybierz Ustaw dystans, aby rozpocząć.', sample_count: 0,
    required_samples: 8, progress_percent: 0, elapsed_s: 0, distance_m: 1, reference_rssi_dbm: null,
    step: 1, total_steps: 3, movement_remaining_s: 0, point_progress_percent: 0, points: [],
    path_loss_exponent: null, fit_rmse_db: null, fit_r_squared: null,
    margin_db: null, median_dbm: null, threshold_dbm: null, mad_db: null,
  };
  private epoch = performance.now();
  private moveUntil = 0;
  private receive?: (state: ViewState) => void;

  async connect(receive: (state: ViewState) => void): Promise<() => void> {
    this.receive = receive;
    this.addEvent('Podgląd uruchomiony. Dane są przykładowe.');
    this.update();
    const timer = setInterval(() => this.update(), 200);
    return () => { clearInterval(timer); this.receive = undefined; };
  }

  async selectDevice(id: string) {
    if (!/^[a-fA-F0-9]{12}$/.test(id)) throw new Error('ID musi mieć 12 znaków hex.');
    this.config.device_id = id.toUpperCase();
    this.history = [];
    this.addEvent('Wybrano brelok w podglądzie.');
    this.update();
  }
  async saveConfig(config: Config) {
    if (!Number.isFinite(config.reference_rssi_dbm) || !Number.isFinite(config.path_loss_exponent)
      || config.path_loss_exponent <= 0 || config.fresh_seconds <= 0
      || config.lost_seconds <= config.fresh_seconds || !Number.isFinite(config.departure_confirm_seconds)
      || config.departure_confirm_seconds < 0.5 || config.departure_confirm_seconds > 5
      || (config.departure_threshold_dbm != null && (!Number.isFinite(config.departure_threshold_dbm)
        || config.departure_threshold_dbm < -110 || config.departure_threshold_dbm > -35))
      || !Number.isFinite(config.calibration_distance_m)
      || config.calibration_distance_m < 0.5 || config.calibration_distance_m > 20) throw new Error('Sprawdź parametry modelu i czasy świeżości.');
    this.config = { ...config };
    this.history = [];
    this.addEvent('Zmieniono parametry podglądu. Plik na dysku nie został zapisany.');
    this.update();
  }
  async setProtection(enabled: boolean) {
    this.addEvent(enabled ? 'ON w podglądzie — bez blokady systemu.' : 'OFF w podglądzie.');
    this.update();
  }
  async openProtectionSettings() { throw new Error('Uprawnienia konfiguruje aplikacja desktopowa.'); }
  async showRunningApplication() { throw new Error('Podgląd nie ma aplikacji w Finderze.'); }
  async startDistanceCalibration() {
    this.moveUntil = performance.now() + 2000;
    this.calibration = { ...this.calibration, status: 'moving_to_point',
      distance_m: 1, step: 1, movement_remaining_s: 2, points: [], progress_percent: 0,
      message: 'DEMO: odejdź na 1 m. Podgląd nie wykonuje fizycznego pomiaru.', sample_count: 0 };
    this.addEvent('DEMO: kalibracja wymaga fizycznego breloka.');
    this.update();
  }
  async captureDistanceCalibration() { throw new Error('Pomiar wymaga fizycznego breloka w aplikacji desktopowej.'); }
  async cancelDistanceCalibration() {
    this.calibration = { ...this.calibration, status: 'idle', message: 'Kalibracja anulowana.' };
    this.update();
  }
  async hide() { throw new Error('Ukrywanie do paska jest dostępne w aplikacji desktopowej.'); }

  private addEvent(label: string) {
    this.events = [...this.events, { id: this.events.length ? this.events[this.events.length - 1].id + 1 : 1,
      time: Date.now(), label, level: 'info' as const }].slice(-100);
  }

  private update() {
    if (this.calibration.status === 'moving_to_point') {
      this.calibration.movement_remaining_s = Math.max(0, (this.moveUntil - performance.now()) / 1000);
      if (this.calibration.movement_remaining_s === 0) {
        this.calibration.status = 'waiting_for_marker';
        this.calibration.message = 'DEMO: potwierdzenie i pomiar wymagają fizycznego breloka w aplikacji desktopowej.';
      }
    }
    const t = (performance.now() - this.epoch) / 1000;
    this.sequence++;
    const raw = Math.round(-58 + Math.sin(t / 6) * 3 + Math.sin(t * 2) * 1.5);
    const filtered = -58 + Math.sin(t / 6) * 2.4;
    const device: Device = {
      device_id: this.config.device_id ?? 'A1B2C3D4E5F6', address: 'DEMO', name: 'Mój brelok',
      state: 'live', telemetry_fresh: true, packet_age_s: 0.2, callback_age_s: 0.2,
      rssi_raw_dbm: raw, rssi_filtered_dbm: filtered,
      distance_estimate_m: 10 ** ((this.config.reference_rssi_dbm - filtered) / (10 * this.config.path_loss_exponent)),
      radial_speed_estimate_m_s: null, actual_speed_m_s: null, motion: 'still', motion_age_s: 12.4,
      motion_age_saturated: false, imu_valid: true, gyro_valid: true,
      acceleration_rms_mg: 12, gyro_rms_dps: 0.8, battery_mv: 3980, packet_hz: 5,
      counters: { callbacks: this.sequence, new_packets: this.sequence, duplicates: 0, skipped_summaries: 0, reboots: 0 },
      last_packet: { protocol_version: 2, device_id: this.config.device_id ?? 'A1B2C3D4E5F6',
        boot_id: 4660, sequence: this.sequence, flags: 22, imu_valid: true, gyro_valid: true,
        clipped: false, battery_valid: true, acceleration_rms_mg: 12, gyro_rms_dps: 0.8,
        motion_age_ms: 12400, motion_age_saturated: false, moving: false, battery_mv: 3980, nominal_tx_dbm: 3,
        button_event_active: false, button_event_count: null },
      trend: { quality: 'insufficient', slope_db_s: null, r_squared: null, coverage: 1, span_s: Math.min(t, 3), points: Math.min(12, this.sequence) },
    };
    this.history = appendSample(this.history, { t_s: t, raw, filtered });
    const snapshot: Snapshot = { t_s: t, mode: 'observe', transport: 'demo', config: { ...this.config },
      selected: device, devices: [device], capabilities: { architecture: 'preview', native_ble: false, os: 'browser', session_lock: false },
      protection: { state: 'disabled', trip_reason: null, lock_attempt: 'none', lock_error: null, far_evidence_s: 0 },
      invalid_packets: 0, transport_errors: 0, last_error: null };
    this.receive?.({ snapshot, history: this.history, events: this.events,
      calibration: { ...this.calibration }, config_error: null });
  }
}
