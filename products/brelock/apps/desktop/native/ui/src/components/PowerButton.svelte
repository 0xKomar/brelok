<script lang="ts">
  import Icon from './Icon.svelte';
  let { on, tripped = false, disabled, busy, preview, onclick }: {
    on: boolean; tripped?: boolean; disabled: boolean; busy: boolean; preview: boolean; onclick: () => void;
  } = $props();
</script>

<div class="power-stage" class:protection-on={on} class:protection-tripped={tripped} class:busy>
  <span class="breath-ring ring-outer" aria-hidden="true"></span>
  <span class="breath-ring ring-inner" aria-hidden="true"></span>
  <button class="power-button" type="button" {disabled} aria-pressed={on}
    aria-label={preview ? (on ? 'Wyłącz ochronę w podglądzie' : 'Włącz ochronę w podglądzie') : tripped ? 'Wyłącz ochronę oczekującą na powrót breloka' : on ? 'Wyłącz ochronę' : 'Włącz ochronę'}
    aria-describedby="protection-description" aria-busy={busy} {onclick}>
    <Icon name="power" size={43} />
    <span class="power-label">{tripped ? 'WAIT' : on ? 'ON' : 'OFF'}</span>
  </button>
</div>
