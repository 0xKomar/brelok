// Wire contract of brelock-core, AppSnapshot and the Tauri host.
export interface Config {
  schema_version: number;
  device_id: string | null;
  reference_rssi_dbm: number;
  path_loss_exponent: number;
  calibration_distance_m: number;
  departure_threshold_dbm: number | null;
  departure_confirm_seconds: number;
  fresh_seconds: number;
  lost_seconds: number;
  refresh_hz: number;
}
export interface Packet {
  protocol_version: number;
  device_id: string;
  boot_id: number;
  sequence: number;
  flags: number;
  imu_valid: boolean;
  gyro_valid: boolean;
  clipped: boolean;
  battery_valid: boolean;
  acceleration_rms_mg: number | null;
  gyro_rms_dps: number | null;
  motion_age_ms: number | null;
  motion_age_saturated: boolean;
  moving: boolean | null;
  battery_mv: number | null;
  nominal_tx_dbm: number;
  button_event_active: boolean;
  button_event_count: number | null;
}
export interface Device {
  device_id: string;
  address: string;
  name: string | null;
  state: 'waiting' | 'live' | 'stale' | 'lost';
  telemetry_fresh: boolean;
  packet_age_s: number | null;
  callback_age_s: number | null;
  rssi_raw_dbm: number | null;
  rssi_filtered_dbm: number | null;
  distance_estimate_m: number | null;
  radial_speed_estimate_m_s: number | null;
  actual_speed_m_s: number | null;
  motion: 'unknown' | 'still' | 'moving';
  motion_age_s: number | null;
  motion_age_saturated: boolean;
  imu_valid: boolean;
  gyro_valid: boolean;
  acceleration_rms_mg: number | null;
  gyro_rms_dps: number | null;
  battery_mv: number | null;
  packet_hz: number | null;
  counters: Record<string, number>;
  last_packet: Packet | null;
  trend: { quality: string; slope_db_s: number | null; r_squared: number | null; coverage: number; span_s: number; points: number };
}
export interface Snapshot {
  t_s: number;
  mode: 'observe' | 'armed' | 'tripped';
  transport: 'starting' | 'scanning' | 'demo' | 'unavailable' | 'stopped';
  config: Config;
  selected: Device | null;
  devices: Device[];
  capabilities: {
    architecture: string; native_ble: boolean; os: string; session_lock: boolean;
    session_lock_supported?: boolean;
    accessibility_trusted?: boolean | null;
    post_event_access?: boolean | null;
    application_path?: string | null;
  };
  protection: {
    state: 'disabled' | 'armed' | 'tripped';
    trip_reason: 'link_lost' | 'hard_far' | 'motion_and_away' | 'sustained_far' | null;
    lock_attempt: 'none' | 'pending' | 'submitted' | 'failed';
    lock_error: string | null;
    far_evidence_s: number;
  };
  invalid_packets: number;
  transport_errors: number;
  last_error: string | null;
}
export interface Sample { t_s: number; raw: number | null; filtered: number | null }
export interface Event { id: number; time: number; label: string; level: 'info' | 'warning' }
export interface CalibrationPoint {
  distance_m: number;
  median_dbm: number;
  threshold_dbm: number;
  mad_db: number;
  margin_db: number;
  sample_count: number;
}
export interface Calibration {
  status: 'idle' | 'moving_to_point' | 'waiting_for_marker' | 'collecting' | 'complete';
  message: string;
  sample_count: number;
  required_samples: number;
  progress_percent: number;
  elapsed_s: number;
  distance_m: number;
  step: number;
  total_steps: number;
  movement_remaining_s: number;
  point_progress_percent: number;
  points: CalibrationPoint[];
  path_loss_exponent: number | null;
  fit_rmse_db: number | null;
  fit_r_squared: number | null;
  reference_rssi_dbm: number | null;
  margin_db: number | null;
  median_dbm: number | null;
  threshold_dbm: number | null;
  mad_db: number | null;
}
export interface ViewState {
  snapshot: Snapshot;
  history: Sample[];
  events: Event[];
  calibration: Calibration;
  config_error: string | null;
  control_connected?: boolean;
  control_error?: string | null;
}
export type Tab = 'status' | 'diagnostics' | 'settings' | 'calibration';
export interface Driver {
  readonly preview: boolean;
  connect(receive: (state: ViewState) => void, navigate: (tab: Tab) => void): Promise<() => void>;
  selectDevice(id: string): Promise<void>;
  saveConfig(config: Config): Promise<void>;
  setProtection(enabled: boolean): Promise<void>;
  openProtectionSettings(): Promise<void>;
  showRunningApplication(): Promise<void>;
  startDistanceCalibration(): Promise<void>;
  captureDistanceCalibration(): Promise<void>;
  cancelDistanceCalibration(): Promise<void>;
  hide(): Promise<void>;
}
