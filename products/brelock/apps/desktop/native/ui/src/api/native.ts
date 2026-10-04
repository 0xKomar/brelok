import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type { Config, Driver, Tab, ViewState } from './types';

export class NativeDriver implements Driver {
  readonly preview = false;
  async connect(receive: (state: ViewState) => void, navigate: (tab: Tab) => void) {
    const unlistenState = await listen<ViewState>('brelock:state', ({ payload }) => receive(payload));
    let unlistenTab: UnlistenFn | undefined;
    try {
      unlistenTab = await listen<Tab>('brelock:navigate', ({ payload }) => navigate(payload));
      receive(await invoke<ViewState>('get_state'));
    } catch (error) { unlistenState(); unlistenTab?.(); throw error; }
    return () => { unlistenState(); unlistenTab?.(); };
  }
  async selectDevice(deviceId: string) { await invoke('select_device', { deviceId }); }
  async saveConfig(config: Config) { await invoke('save_config', { config }); }
  async setProtection(enabled: boolean) { await invoke('set_protection', { enabled }); }
  async openProtectionSettings() { await invoke('open_protection_settings'); }
  async showRunningApplication() { await invoke('show_running_application'); }
  async startDistanceCalibration() { await invoke('start_distance_calibration'); }
  async captureDistanceCalibration() { await invoke('capture_distance_calibration'); }
  async cancelDistanceCalibration() { await invoke('cancel_distance_calibration'); }
  async hide() { await invoke('hide_window'); }
}
