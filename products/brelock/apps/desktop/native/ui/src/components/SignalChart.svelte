<script lang="ts">
  import type { Sample } from '../api/types';
  import { graphPaths } from '../state/presentation';
  let { history }: { history: Sample[] } = $props();
  const raw = $derived(graphPaths(history, 'raw'));
  const filtered = $derived(graphPaths(history, 'filtered'));
</script>

<div class="signal-chart">
  <div class="chart-heading"><span>Siła sygnału</span><span class="dim">ostatnie 60 s</span></div>
  <svg viewBox="0 0 320 112" role="img" aria-label="Wykres RSSI: sygnał surowy i filtrowany. Przerwy oznaczają brak aktualnych danych.">
    {#each [20, 52, 84] as y}<line x1="0" x2="320" y1={y} y2={y} stroke="#24334b" stroke-dasharray="3 5" />{/each}
    {#each raw as d}<path {d} fill="none" stroke="#415775" stroke-width="1.4" />{/each}
    {#each filtered as d}<path {d} fill="none" stroke="#8ba7d6" stroke-width="2" />{/each}
  </svg>
  <div class="chart-legend"><span><i class="raw-line"></i> Surowy</span><span><i class="filtered-line"></i> Filtrowany</span><span class="dim">dBm</span></div>
</div>
