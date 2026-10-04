<script lang="ts">
  import { onMount } from 'svelte';
  import { isTauri } from '@tauri-apps/api/core';
  import { NativeDriver } from './api/native';
  import { PreviewDriver } from './api/preview';
  import type { Config, Driver, Tab, ViewState } from './api/types';
  import { defaultConfig, protectionCanAttempt, value } from './state/presentation';
  import Icon from './components/Icon.svelte';
  import PowerButton from './components/PowerButton.svelte';
  import SignalChart from './components/SignalChart.svelte';

  const driver: Driver = isTauri() ? new NativeDriver() : new PreviewDriver();
  let tab = $state<Tab>('status');
  let viewState = $state<ViewState | null>(null);
  let previewOn = $state(false);
  let busy = $state(false);
  let message = $state('');
  let draft = $state<Config>(defaultConfig());
  let idInput = $state('');
  let signature = $state('');
  let mainElement = $state<HTMLElement>();
  let lastNavigationKey = '';
  const snapshot = $derived(viewState?.snapshot);
  const device = $derived(snapshot?.selected);
  const calibrationActive = $derived(viewState?.calibration.status === 'moving_to_point'
    || viewState?.calibration.status === 'waiting_for_marker'
    || viewState?.calibration.status === 'collecting');
  const canAttempt = $derived(!calibrationActive && snapshot ? protectionCanAttempt(snapshot, driver.preview) : false);
  const needsPermission = $derived(!driver.preview && snapshot?.capabilities.os === 'macos'
    && !snapshot.capabilities.session_lock);
  const canCalibrate = $derived(driver.preview || Boolean(snapshot?.transport === 'scanning'
    && device != null
    && device.rssi_filtered_dbm != null
    && device.packet_age_s != null && device.packet_age_s <= 3));
  const armed = $derived(snapshot?.protection.state === 'armed');
  const tripped = $derived(snapshot?.protection.state === 'tripped');
  const on = $derived(driver.preview ? previewOn : armed || tripped);
  const live = $derived(device?.telemetry_fresh ?? false);
  const tripLabels: Record<string, string> = {
    link_lost: 'brak świeżych pakietów breloka (L1)',
    hard_far: 'bardzo słaby sygnał (L2)',
    motion_and_away: 'ruch breloka i trend oddalania (L3)',
    sustained_far: 'utrzymujący się słaby sygnał (L4)',
  };
  const protectionTitle = $derived(driver.preview
    ? (on ? 'Ochrona włączona' : 'Ochrona wyłączona')
    : armed ? 'Ochrona włączona' : tripped ? 'Ochrona czeka na powrót' : 'Ochrona wyłączona');
  const protectionMessage = $derived.by(() => {
    if (driver.preview) return on ? 'Podgląd ON · bez blokady komputera.' : 'Kliknij, aby zobaczyć ON w podglądzie.';
    if (calibrationActive) return 'Kalibracja trwa. Zakończ pomiar lub anuluj go, aby włączyć ochronę.';
    if (armed) return 'Ochrona uzbrojona · komputer zostanie zablokowany po spełnieniu reguły L1–L4.';
    if (tripped) {
      const reason = snapshot?.protection.trip_reason;
      if (snapshot?.protection.lock_attempt === 'failed') return `Reguła ${tripLabels[reason ?? ''] ?? 'odejścia'} · ${snapshot.protection.lock_error ?? 'system odrzucił blokadę'}. Ochrona czeka na powrót breloka.`;
      if (snapshot?.protection.lock_attempt === 'submitted') return `Reguła ${tripLabels[reason ?? ''] ?? 'odejścia'} · wysłano żądanie blokady. Ochrona uzbroi się ponownie, gdy wrócisz z brelokiem.`;
      return `Spełniona reguła ${tripLabels[reason ?? ''] ?? 'odejścia'} · wysyłam żądanie blokady.`;
    }
    if (!snapshot?.capabilities.session_lock) {
      return snapshot?.capabilities.os === 'macos'
        ? 'Nadaj Dostępność tej wersji: breLock PoC. ON rozpocznie konfigurację zgody.'
        : 'Natywna blokada jest dostępna w tej wersji na macOS i Windows.';
    }
    if (!snapshot?.config.device_id) return 'Wybierz brelok w Ustawieniach, aby włączyć ochronę.';
    if (snapshot.transport !== 'scanning') return 'Czekam na aktywne skanowanie Bluetooth.';
    if (device?.state !== 'live' || !device.telemetry_fresh) return 'Połącz brelok i poczekaj na świeże pakiety.';
    if (device.rssi_filtered_dbm == null) return 'Czekam na stabilne próbki sygnału RSSI.';
    return 'Komputer nie jest chroniony. Naciśnij przycisk, aby uzbroić ochronę.';
  });
  const motion = $derived(!live || device?.motion === 'unknown' ? 'Nieznany' : device?.motion === 'moving' ? 'W ruchu' : 'Spoczynek');
  const connection = $derived(snapshot?.transport === 'unavailable' ? 'Brak dostępu do BLE'
    : live ? 'Telemetria aktualna' : device?.state === 'lost' ? 'Brelok niewykryty'
    : device?.state === 'stale' ? 'Dane nieaktualne' : device ? 'Czekam na brelok' : 'Wybierz swój brelok');

  $effect(() => {
    if (snapshot) {
      const next = JSON.stringify(snapshot.config);
      if (next !== signature) {
        signature = next;
        draft = { ...snapshot.config };
        idInput = snapshot.config.device_id ?? '';
      }
    }
  });

  $effect(() => {
    const key = `${tab}:${tab === 'calibration' ? viewState?.calibration.step : ''}:${tab === 'calibration' && viewState?.calibration.status === 'complete' ? 'done' : ''}`;
    if (mainElement && key !== lastNavigationKey) {
      lastNavigationKey = key;
      mainElement.scrollTop = 0;
    }
  });

  onMount(() => {
    let closed = false;
    let cleanup: (() => void) | undefined;
    driver.connect((next) => {
      if (!closed) {
        const previous = viewState?.calibration.status;
        viewState = next;
        if (((next.calibration.status === 'moving_to_point' || next.calibration.status === 'waiting_for_marker') && (previous === 'idle' || previous === 'complete'))
          || (next.calibration.status === 'collecting' && previous !== 'collecting')) tab = 'calibration';
      }
    }, (next) => { if (!closed) tab = next; })
      .then((stop) => { if (closed) stop(); else cleanup = stop; })
      .catch((error) => { if (!closed) message = String(error); });
    return () => { closed = true; cleanup?.(); };
  });

  async function action(task: () => Promise<void>, success = '') {
    if (busy) return;
    busy = true;
    message = '';
    try { await task(); if (success) message = success; }
    catch (error) { message = error instanceof Error ? error.message : String(error); }
    finally { busy = false; }
  }
  async function toggle() {
    const enable = !on;
    await action(async () => {
      await driver.setProtection(enable);
      if (driver.preview) previewOn = enable;
    }, enable ? 'Ochrona uzbrojona.' : 'Ochrona wyłączona.');
  }
  async function beginCalibration() {
    if (busy) return;
    busy = true;
    message = '';
    try {
      await driver.startDistanceCalibration();
      tab = 'calibration';
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    } finally { busy = false; }
  }
  async function endCalibration() {
    if (viewState?.calibration.status !== 'complete') {
      await action(() => driver.cancelDistanceCalibration());
    }
    tab = 'status';
  }
  async function select(id: string) {
    await action(() => driver.selectDevice(id), 'Brelok został wybrany.');
  }
  async function save() {
    await action(async () => {
      await driver.saveConfig({ ...draft });
    }, driver.preview ? 'Parametry podglądu zapisane na tę sesję.' : 'Ustawienia zapisane lokalnie.');
  }
  async function copyReport() {
    await action(() => navigator.clipboard.writeText(JSON.stringify(viewState, null, 2)), 'Diagnostyka skopiowana.');
  }
</script>

<svelte:head><title>breLock — {driver.preview ? 'podgląd' : 'desktop'}</title></svelte:head>

<div class="app-shell">
  <header class="app-header">
    <div class="brand"><span class="brand-mark"><Icon name="shield" size={17} /></span><span>bre<span class="brand-light">Lock</span></span></div>
    <div class="header-actions">
      {#if driver.preview}<span class="demo-badge" title="Podgląd interfejsu, bez ochrony systemu">DEMO</span>{/if}
      {#if !driver.preview}<button class="icon-button" title="Ukryj okno. Aplikacja działa dalej w tle." aria-label="Ukryj okno" onclick={() => action(() => driver.hide())}><Icon name="hide" size={17} /></button>{/if}
    </div>
  </header>

  <nav class="tabs" aria-label="Widoki aplikacji">
    <button class:active={tab === 'status'} aria-current={tab === 'status' ? 'page' : undefined} onclick={() => tab = 'status'}><Icon name="shield" size={15} />Status</button>
    <button class:active={tab === 'diagnostics'} aria-current={tab === 'diagnostics' ? 'page' : undefined} onclick={() => tab = 'diagnostics'}><Icon name="activity" size={15} />Diagnostyka</button>
    <button class:active={tab === 'settings'} aria-current={tab === 'settings' ? 'page' : undefined} onclick={() => tab = 'settings'}><Icon name="settings" size={15} />Ustawienia</button>
  </nav>

  {#if message}<div class="notice" role="status"><span>{message}</span><button aria-label="Zamknij komunikat" onclick={() => message = ''}>×</button></div>{/if}
  {#if viewState?.config_error}<div class="notice warning" role="alert">Konfiguracja wymaga poprawienia: {viewState.config_error}</div>{/if}

  <main bind:this={mainElement}>
    {#if tab === 'status'}
      <section class="status-view" aria-label="Status ochrony">
        <div class="protection-hero" class:protection-on={on} class:protection-tripped={tripped}>
          <p class="eyebrow">TWÓJ KOMPUTER</p>
          <PowerButton {on} {tripped} disabled={busy || (!canAttempt && !on)} {busy} preview={driver.preview} onclick={toggle} />
          <h1>{protectionTitle}</h1>
          <p id="protection-description" class="hero-description">{protectionMessage}</p>
        </div>

        {#if needsPermission}
          <div class="permission-card">
            <strong>Dostęp dla breLock PoC</strong>
            <p>Dodaj tę aplikację w Dostępności. Włączony wpis starszej kopii breLock może dotyczyć innego programu. Po zmianie zamknij i otwórz aplikację.</p>
            <div class="permission-actions">
              <button class="small-button" disabled={busy} onclick={() => action(() => driver.openProtectionSettings())}>Otwórz Dostępność</button>
              <button class="small-button" disabled={busy} onclick={() => action(() => driver.showRunningApplication())}>Pokaż tę aplikację</button>
            </div>
          </div>
        {/if}

        <button class="device-card" onclick={() => tab = 'settings'} aria-label="Wybierz lub zmień brelok">
          <span class="device-icon"><Icon name="key" size={19} /></span>
          <span class="device-info"><strong>{device ? 'Brelok Waveshare' : 'Twój brelok'}</strong><span class="device-sub"><i class:live></i>{connection}</span></span>
          <span class="device-id">{device ? `…${device.device_id.slice(-4)}` : 'Wybierz'}</span><Icon name="chevron" size={13} />
        </button>

        <button class="setup-card" onclick={beginCalibration} disabled={busy || !canCalibrate}>
          <span class="setup-mark"><Icon name="touch" size={17} /></span>
          <span><strong>{calibrationActive ? 'Wróć do kalibracji' : 'Kalibracja 1 → 2 → 3 m'}</strong><small>{canCalibrate ? 'Dopasowanie metrów, współczynnika n i progu' : device ? 'Czekam na świeży, stabilny sygnał breloka' : 'Najpierw wybierz brelok w Ustawieniach'}</small></span>
          <Icon name="chevron" size={14} />
        </button>

        <div class="metric-grid">
          <div class="metric"><span class="metric-label"><Icon name="signal" size={13} />Sygnał</span><strong>{value(device?.rssi_filtered_dbm, 0, 'dBm')}</strong></div>
          <div class="metric"><span class="metric-label"><Icon name="activity" size={13} />Ruch</span><strong>{motion}</strong></div>
          <div class="metric"><span class="metric-label"><Icon name="battery" size={13} />Bateria</span><strong>{value(live && device?.battery_mv != null ? device.battery_mv / 1000 : null, 2, 'V')}</strong></div>
          <div class="metric"><span class="metric-label"><Icon name="clock" size={13} />Wiek pakietu</span><strong>{value(device?.packet_age_s, 1, 's')}</strong></div>
        </div>
        {#if tripped && snapshot?.protection.lock_attempt === 'failed'}<p class="inline-warning"><Icon name="info" size={14} />Blokada nie została wysłana. Sprawdź uprawnienia systemowe i uzbrój ochronę ponownie.</p>{/if}
        {#if snapshot?.transport === 'unavailable'}<p class="inline-warning"><Icon name="info" size={14} />{snapshot.last_error?.includes('Permission') ? 'Nadaj aplikacji uprawnienie Bluetooth w ustawieniach systemu.' : snapshot.last_error ?? 'Bluetooth jest niedostępny.'}</p>{/if}
        <button class="text-action" onclick={() => tab = 'diagnostics'}>Sprawdź pomiary<Icon name="chevron" size={12} /></button>
      </section>
    {:else if tab === 'diagnostics'}
      <section class="details-view" aria-label="Diagnostyka">
        <div class="view-heading"><div><p class="eyebrow">POMIARY NA ŻYWO</p><h1>Diagnostyka</h1></div><button class="icon-button" title="Kopiuj raport diagnostyczny" aria-label="Kopiuj raport diagnostyczny" onclick={copyReport} disabled={!viewState || busy}><Icon name="download" size={17} /></button></div>
        <SignalChart history={viewState?.history ?? []} />
        <div class="data-panel">
          <h2>Reguły ochrony</h2>
          <dl>
            <div><dt>Stan</dt><dd>{snapshot?.protection.state === 'armed' ? 'Uzbrojona' : snapshot?.protection.state === 'tripped' ? 'Czeka na powrót breloka' : 'Wyłączona'}</dd></div>
            <div><dt>Powód ostatniej decyzji</dt><dd>{snapshot?.protection.trip_reason ? `${tripLabels[snapshot.protection.trip_reason] ?? snapshot.protection.trip_reason}` : '—'}</dd></div>
            <div><dt>Wynik żądania OS</dt><dd>{snapshot?.protection.lock_attempt === 'submitted' ? 'Wysłano · bez potwierdzenia' : snapshot?.protection.lock_attempt === 'failed' ? 'Błąd' : snapshot?.protection.lock_attempt === 'pending' ? 'Wysyłanie' : '—'}</dd></div>
            <div><dt>Dowód L4</dt><dd>{value(snapshot?.protection.far_evidence_s, 1, 's')}</dd></div>
          </dl>
        </div>
        <div class="data-panel">
          <h2>Radio i dystans</h2>
          <dl>
            <div><dt>RSSI surowe / filtrowane</dt><dd>{value(device?.rssi_raw_dbm)} / {value(device?.rssi_filtered_dbm, 1)} <span>dBm</span></dd></div>
            <div><dt>Dystans szacowany</dt><dd>{value(device?.distance_estimate_m, 2, 'm')}</dd></div>
            <div><dt>Zmiana dystansu z RSSI</dt><dd>{value(device?.radial_speed_estimate_m_s, 2, 'm/s')}</dd></div>
            <div><dt>Trend</dt><dd>{value(device?.trend.slope_db_s, 2, 'dB/s')}</dd></div>
            <div><dt>Jakość dopasowania R²</dt><dd>{value(device?.trend.r_squared, 2)}</dd></div>
          </dl><p class="field-note">Metry i prędkość radialna to estymacje sygnału. Rzeczywista prędkość nie jest mierzona.</p>
        </div>
        <details class="data-panel" open><summary>Ruch i bateria</summary><dl>
          <div><dt>Przyspieszenie RMS</dt><dd>{value(device?.acceleration_rms_mg, 0, 'mg')}</dd></div>
          <div><dt>Żyroskop RMS</dt><dd>{value(device?.gyro_rms_dps, 1, '°/s')}</dd></div>
          <div><dt>Ostatni ruch</dt><dd>{value(device?.motion_age_s, 1, 's')}</dd></div>
          <div><dt>IMU / żyroskop</dt><dd>{device?.imu_valid ? 'OK' : '—'} / {device?.gyro_valid ? 'OK' : '—'}</dd></div>
          <div><dt>Bateria</dt><dd>{value(device?.battery_mv, 0, 'mV')}</dd></div>
        </dl></details>
        <details class="data-panel"><summary>Pakiety i odbiór</summary><dl>
          <div><dt>Ekran i sterowanie breloka</dt><dd>{viewState?.control_connected ? 'Połączone · GATT' : 'Brak kanału zwrotnego'}</dd></div>
          <div><dt>Nowe pakiety</dt><dd>{value(device?.packet_hz, 1, '/s')}</dd></div>
          <div><dt>Sequence / boot ID</dt><dd>{device?.last_packet?.sequence ?? '—'} / {device?.last_packet?.boot_id ?? '—'}</dd></div>
          <div><dt>Duplikaty</dt><dd>{device?.counters.duplicates ?? 0}</dd></div>
          <div><dt>Pominięte podsumowania</dt><dd>{device?.counters.skipped_summaries ?? 0}</dd></div>
          <div><dt>Błędy transportu</dt><dd>{snapshot?.transport_errors ?? 0}</dd></div>
          <div><dt>Niepoprawne pakiety</dt><dd>{snapshot?.invalid_packets ?? 0}</dd></div>
        </dl>{#if viewState?.control_error}<p class="field-note">Kanał sterowania: {viewState.control_error}</p>{/if}{#if snapshot?.last_error}<p class="field-note">Ostatni błąd: {snapshot.last_error}</p>{/if}</details>
        <div class="data-panel"><h2>Ostatnie zdarzenia</h2><ul class="events">{#each [...(viewState?.events ?? [])].reverse() as event (event.id)}<li><time>{new Date(event.time).toLocaleTimeString('pl-PL')}</time><span>{event.label}</span></li>{:else}<li class="dim">Czekam na zdarzenia.</li>{/each}</ul></div>
      </section>
    {:else if tab === 'calibration'}
      <section class="details-view calibration-view" aria-label="Kalibracja w trzech punktach">
        <div class="view-heading"><div><p class="eyebrow">KREATOR POMIARU</p><h1>Kalibracja 1 → 2 → 3 m</h1></div><button class="icon-button" aria-label="Wróć do statusu" onclick={endCalibration}><Icon name="chevron" size={17} /></button></div>
        {#if viewState?.calibration.status === 'complete'}
          <div class="calibration-success">
            <span class="success-mark"><Icon name="check" size={24} /></span>
            <h2>Model skalibrowany</h2>
            <p>{viewState.calibration.message}</p>
            <div class="calibration-results">
              <div><span>RSSI przy 1 m</span><strong>{value(viewState.calibration.reference_rssi_dbm, 1, 'dBm')}</strong></div>
              <div><span>Współczynnik n</span><strong>{value(viewState.calibration.path_loss_exponent, 2)}</strong></div>
              <div><span>Próg odejścia</span><strong>{value(viewState.calibration.threshold_dbm, 1, 'dBm')}</strong></div>
            </div>
            <div class="calibration-point-results">
              {#each viewState.calibration.points as point (point.distance_m)}
                <div><strong>{point.distance_m} m</strong><span>{value(point.median_dbm, 1, 'dBm')}</span><small>Wahanie {value(point.mad_db, 1, 'dB')} · {point.sample_count} próbek</small></div>
              {/each}
            </div>
            <p class="field-note">Błąd dopasowania: {value(viewState.calibration.fit_rmse_db, 2, 'dB')}. Próg wyznaczono z punktu 3 m, z marginesem {value(viewState.calibration.margin_db, 1, 'dB')}. Metry pozostają szacunkiem BLE.</p>
            <button class="save-button" onclick={endCalibration}>Gotowe<Icon name="check" size={15} /></button>
          </div>
        {:else}
          <div class="calibration-stations" aria-label="Punkty pomiaru">
            {#each [1, 2, 3] as distance}
              {@const point = viewState?.calibration.points.find((p) => p.distance_m === distance)}
              <div class:current={viewState?.calibration.step === distance} class:done={point != null}>
                <strong>{distance} m</strong><span>{point ? value(point.median_dbm, 1, 'dBm') : viewState?.calibration.step === distance ? 'Teraz' : 'Następny'}</span>
              </div>
            {/each}
          </div>
          <div class="calibration-position">
            <p>KROK {viewState?.calibration.step ?? 1} Z 3</p>
            <strong>{value(viewState?.calibration.distance_m ?? 1, 0, 'm')}</strong>
            {#if viewState?.calibration.status === 'moving_to_point'}
              <h2>{viewState.calibration.step === 1 ? 'Odejdź na pierwszy punkt' : 'Cofnij się o kolejny metr'}</h2>
              <span class="calibration-countdown">{Math.ceil(viewState.calibration.movement_remaining_s)} s</span>
            {:else if viewState?.calibration.status === 'collecting'}
              <h2>Pozostań w miejscu</h2><span>Pomiar punktu · {viewState.calibration.point_progress_percent}%</span>
            {:else}<h2>Potwierdź swoją pozycję</h2><span>Przytrzymaj POMIAR na breloku przez 3 s</span>{/if}
          </div>
          <p class="field-note">Wyznacz 1, 2 i 3 m od laptopa ustawionego na stole. Po odliczaniu potwierdź pozycję. Każdy pomiar trwa 12–35 s; trzymaj brelok tak, jak zwykle go nosisz.</p>
          <div class="calibration-progress">
            <div><span>Postęp całej serii</span><strong>{viewState?.calibration.progress_percent ?? 0}%</strong></div>
            <span class="progress-track"><i style={`width:${Math.min(100, viewState?.calibration.progress_percent ?? 0)}%`}></i></span>
            <p>{viewState?.calibration.message ?? 'Oczekiwanie na dane breloka…'}</p>
            {#if viewState?.calibration.status === 'collecting'}<p>{value(viewState.calibration.elapsed_s, 0, 's')} · {viewState.calibration.sample_count} prawdziwych odczytów · minimum {viewState.calibration.required_samples}</p>{/if}
          </div>
          <div class="calibration-device"><span class="setup-mark"><Icon name="touch" size={20} /></span><span><strong>{device ? `Brelok …${device.device_id.slice(-4)}` : 'Brak wybranego breloka'}</strong><small>START na breloku również wymaga przytrzymania przez 3 s.</small></span></div>
          {#if viewState?.calibration.status === 'waiting_for_marker'}<button class="calibration-start" disabled={busy || driver.preview || !canCalibrate} onclick={() => action(() => driver.captureDistanceCalibration())}>Jestem na {viewState.calibration.distance_m} m — rozpocznij pomiar</button>{/if}
          <button class="cancel-button" onclick={endCalibration}>Anuluj kalibrację</button>
        {/if}
      </section>
    {:else}
      <section class="details-view" aria-label="Ustawienia">
        <div class="view-heading"><div><p class="eyebrow">LOKALNIE NA TYM KOMPUTERZE</p><h1>Ustawienia</h1></div></div>
        <div class="data-panel"><h2>Twój brelok</h2><p class="field-note">Wybierz pełny ID urządzenia. Skanowanie działa w tle.</p>
          <label for="device-id">ID breloka</label><div class="input-action"><input id="device-id" bind:value={idInput} maxlength="12" placeholder="A1B2C3D4E5F6" autocomplete="off" spellcheck="false" /><button class="small-button" onclick={() => select(idInput.trim().toUpperCase())} disabled={busy || !/^[a-fA-F0-9]{12}$/.test(idInput.trim())}>Użyj</button></div>
          <div class="discovered">{#each snapshot?.devices ?? [] as found (found.device_id)}<button class:selected={found.device_id === snapshot?.config.device_id} onclick={() => select(found.device_id)} disabled={busy}><span><Icon name="key" size={15} /><code>{found.device_id}</code></span><span>{value(found.rssi_filtered_dbm, 0, 'dBm')}{#if found.device_id === snapshot?.config.device_id}<Icon name="check" size={14} />{/if}</span></button>{:else}<p class="field-note">{snapshot?.transport === 'unavailable' ? 'Sprawdź uprawnienia Bluetooth.' : 'Jeszcze nie wykryto urządzenia.'}</p>{/each}</div>
        </div>
        <form class="data-panel settings-form" onsubmit={(event) => { event.preventDefault(); void save(); }}>
          <h2>Model i próg odejścia</h2><p class="field-note">Kreator 1/2/3 m dopasowuje RSSI przy 1 m oraz współczynnik n. Domyślny próg ochrony pochodzi z ostatniego punktu; możesz go ręcznie nadpisać niżej.</p>
          <div class="setting-status"><span>Próg ochrony</span><span class="muted-tag">{value(snapshot?.config.departure_threshold_dbm, 1, 'dBm')}</span></div>
          <div class="form-grid"><label>Potwierdzenie odejścia <span>s</span><input type="number" bind:value={draft.departure_confirm_seconds} min="0.5" max="5" step="0.1" required /></label><label>Ręczny próg blokady <span>dBm</span><input type="number" bind:value={draft.departure_threshold_dbm} min="-110" max="-35" step="0.5" placeholder="START" /></label></div>
          <p class="field-note">Krótsze potwierdzenie blokuje szybciej (0,5–5 s). Próg dBm zastępuje próg z kalibracji: mniej ujemny, np. −40, blokuje bliżej komputera; pole puste używa wartości START. Utrata połączenia ma osobny czas poniżej.</p>
          <div class="form-grid"><label>RSSI przy 1 m <span>dBm</span><input type="number" bind:value={draft.reference_rssi_dbm} min="-127" max="20" step="1" required /></label><label>Współczynnik n<input type="number" bind:value={draft.path_loss_exponent} min="0.1" max="10" step="0.1" required /></label></div>
          <div class="setting-status"><span>Ostatni punkt kalibracji</span><span class="muted-tag">{value(snapshot?.config.calibration_distance_m, 1, 'm')}</span></div>
          <div class="form-grid"><label>Świeżość danych <span>s</span><input type="number" bind:value={draft.fresh_seconds} min="0.1" max="30" step="0.1" required /></label><label>Utrata sygnału <span>s</span><input type="number" bind:value={draft.lost_seconds} min="0.2" max="120" step="0.1" required /></label></div>
          <button class="save-button" type="submit" disabled={busy}>Zapisz ustawienia<Icon name="check" size={15} /></button>
        </form>
        <div class="data-panel"><h2>Działanie aplikacji</h2><p class="field-note">{driver.preview ? 'Podgląd działa w przeglądarce. Ikona na pasku i ukrywanie okna są dostępne w wersji desktopowej.' : 'Zamknięcie okna ukrywa je do ikony na pasku. Odbiór i analiza nadal działają w tle.'}</p><div class="setting-status"><span>Blokada systemu</span><span class="muted-tag">{snapshot?.capabilities.session_lock ? 'Dostępna' : snapshot?.capabilities.os === 'macos' ? 'Wymaga Dostępności' : 'Niedostępna'}</span></div><div class="setting-status"><span>Próg z kalibracji</span><span class="muted-tag">{snapshot?.config.departure_threshold_dbm == null ? 'Używane wartości START' : 'Zapisany lokalnie'}</span></div>
          {#if snapshot?.capabilities.os === 'macos'}
            <div class="setting-status"><span>Dostępność tej kopii</span><span class="muted-tag">{snapshot.capabilities.accessibility_trusted ? 'Przyznana' : 'Brak zgody'}</span></div>
            <div class="setting-status"><span>Wysyłanie skrótu blokady</span><span class="muted-tag">{snapshot.capabilities.post_event_access ? 'Dostępne' : 'Brak zgody'}</span></div>
            {#if snapshot.capabilities.application_path}<p class="field-note">Uruchomiona aplikacja:<code class="application-path">{snapshot.capabilities.application_path}</code></p>{/if}
          {/if}
        </div>
      </section>
    {/if}
  </main>

  <footer class="app-footer"><span><i class:preview-dot={driver.preview}></i>{driver.preview ? 'Dane przykładowe · bez blokady OS' : armed ? 'Działa w tle · ochrona uzbrojona' : tripped ? 'Działa w tle · aktywna, czeka na powrót' : 'Działa w tle · ochrona wyłączona'}</span><span>v0.1</span></footer>
</div>
