import type { Sample, Snapshot } from '../api/types';

export function value(number: number | null | undefined, digits = 0, unit = ''): string {
  if (number == null || !Number.isFinite(number)) return '—';
  return `${number.toLocaleString('pl-PL', { minimumFractionDigits: digits, maximumFractionDigits: digits })}${unit ? ` ${unit}` : ''}`;
}

export function protectionAvailable(snapshot: Snapshot, preview: boolean): boolean {
  if (preview) return true;
  return snapshot.capabilities.session_lock && protectionCanAttempt(snapshot, false);
}

// Missing OS consent must not disable the very button that starts consent
// setup. The native host still refuses to arm until permission is granted.
export function protectionCanAttempt(snapshot: Snapshot, preview: boolean): boolean {
  if (preview) return true;
  const device = snapshot.selected;
  const supported = snapshot.capabilities.session_lock_supported
    ?? ['macos', 'windows'].includes(snapshot.capabilities.os);
  return supported
    && snapshot.config?.device_id != null
    && snapshot.transport === 'scanning'
    && device?.state === 'live'
    && device.telemetry_fresh
    && device.rssi_filtered_dbm != null;
}

export function appendSample(history: Sample[], sample: Sample): Sample[] {
  return [...history.filter((point) => point.t_s >= sample.t_s - 60), sample].slice(-301);
}

export function graphPaths(history: Sample[], field: 'raw' | 'filtered'): string[] {
  if (!history.length) return [];
  const end = history[history.length - 1].t_s;
  const segments: string[] = [];
  let path = '';
  let previous: number | undefined;
  for (const point of history) {
    const number = point[field];
    if (number == null || !Number.isFinite(number) || (previous != null && point.t_s - previous > 1.5)) {
      if (path) segments.push(path);
      path = '';
    }
    if (number != null && Number.isFinite(number)) {
      const x = Math.max(0, Math.min(320, (point.t_s - end + 60) / 60 * 320));
      const y = Math.max(4, Math.min(104, (-35 - number) / 60 * 100 + 4));
      path += `${path ? ' L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    }
    previous = point.t_s;
  }
  if (path) segments.push(path);
  return segments;
}

export const defaultConfig = (): Snapshot['config'] => ({
  schema_version: 1, device_id: null, reference_rssi_dbm: -59, departure_threshold_dbm: null,
  path_loss_exponent: 2.2, calibration_distance_m: 3, departure_confirm_seconds: 0.7,
  fresh_seconds: 1.5, lost_seconds: 3, refresh_hz: 5,
});
