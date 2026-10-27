<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  let {
    tone = 'info',
    title = '',
    children,
  }: {
    tone?: 'info' | 'warning' | 'error' | 'success';
    title?: string;
    children?: Snippet;
  } = $props();
</script>

<div class="notice {tone}" role={tone === 'error' ? 'alert' : undefined}>
  <Icon
    name={tone === 'success'
      ? 'circleCheck'
      : tone === 'warning' || tone === 'error'
        ? 'warning'
        : 'info'}
    size={20}
  />
  <div>
    {#if title}<strong>{title}</strong>{/if}{#if children}<div class="notice-copy">
        {@render children()}
      </div>{/if}
  </div>
</div>
