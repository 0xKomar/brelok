import { describe, expect, it } from 'vitest';
import { appendSample, defaultConfig, graphPaths, protectionAvailable, protectionCanAttempt, value } from './presentation';
import type { Snapshot } from '../api/types';

describe('measurement presentation', () => {
  it('does not turn missing or non-finite telemetry into a zero reading', () => {
    for (const missing of [null, undefined, NaN, Infinity]) expect(value(missing, 2, 'm')).toBe('—');
    expect(value(0, 1, 'm/s')).toBe('0,0 m/s');
  });
  it('does not allow the OBSERVE backend to claim enabled protection', () => {
    const snapshot = { mode: 'observe', capabilities: { session_lock: false } } as Snapshot;
    expect(protectionAvailable(snapshot, false)).toBe(false);
    expect(protectionAvailable({ ...snapshot, capabilities: { ...snapshot.capabilities, session_lock: true } }, false)).toBe(false);
    expect(protectionAvailable(snapshot, true)).toBe(true);
  });
  it('breaks the chart at lost data and callback gaps', () => {
    const paths = graphPaths([
      { t_s: 0, raw: -58, filtered: -59 }, { t_s: .2, raw: -59, filtered: -59 },
      { t_s: .4, raw: null, filtered: null }, { t_s: .6, raw: -60, filtered: -60 },
      { t_s: 4, raw: -62, filtered: -62 },
    ], 'filtered');
    expect(paths).toHaveLength(3);
    expect(paths.filter((path) => path.includes(' L'))).toHaveLength(1);
  });
  it('keeps ON usable to request macOS consent while actual protection remains unavailable', () => {
    const snapshot = {
      config: { ...defaultConfig(), device_id: '142D6F020F3C' },
      transport: 'scanning',
      selected: { state: 'live', telemetry_fresh: true, rssi_filtered_dbm: -55 },
      capabilities: { os: 'macos', session_lock: false, session_lock_supported: true },
    } as Snapshot;
    expect(protectionCanAttempt(snapshot, false)).toBe(true);
    expect(protectionAvailable(snapshot, false)).toBe(false);
    expect(protectionAvailable({ ...snapshot, capabilities: { ...snapshot.capabilities, session_lock: true } }, false)).toBe(true);
    expect(protectionCanAttempt({ ...snapshot, transport: 'unavailable' }, false)).toBe(false);
    expect(protectionCanAttempt({ ...snapshot, selected: { ...snapshot.selected!, telemetry_fresh: false } }, false)).toBe(false);
    expect(protectionCanAttempt({ ...snapshot, capabilities: { ...snapshot.capabilities, session_lock_supported: false } }, false)).toBe(false);
  });
  it('retains a bounded history after long and dense sessions', () => {
    const history = Array.from({ length: 1000 }, (_, i) => ({ t_s: i / 20, raw: -60, filtered: -60 }));
    expect(appendSample(history, { t_s: 90, raw: null, filtered: null })).toHaveLength(301);
    expect(appendSample(history, { t_s: 180, raw: null, filtered: null })).toHaveLength(1);
  });
});
