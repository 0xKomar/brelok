<script lang="ts">
  let { name, size = 18 }: { name: string; size?: number } = $props();
  const paths: Record<string, string> = {
    shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z',
    power: 'M12 2v10 M6.4 5.7a8.5 8.5 0 1 0 11.2 0',
    signal: 'M4 20v-3 M9 20v-7 M14 20V9 M19 20V4',
    activity: 'M2 12h5l3-8 4 16 3-8h5',
    battery: 'M4 7h14v10H4V7Z M21 10v4 M7 10v4 M10 10v4 M13 10v4',
    clock: 'M12 8v4l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
    settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z',
    chevron: 'm9 5 7 7-7 7',
    hide: 'M5 12h14 M12 5l7 7-7 7',
    check: 'm5 12 4 4 10-10',
    key: 'M14 5a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z M9 13l-6 6v2h3v-3h3l2-3',
    info: 'M12 11v6 M12 7h.01 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
    download: 'M12 3v12 m-5-5 5 5 5-5 M4 16v5h16v-5',
    touch: 'M8 11V5a2 2 0 1 1 4 0v5-2a2 2 0 1 1 4 0v3-1a2 2 0 1 1 4 0v5c0 4-2 7-6 7h-2c-2 0-3-1-4-2l-4-4a2 2 0 0 1 3-3l1 1',
  };
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={paths[name] ?? paths.info} />
</svg>
