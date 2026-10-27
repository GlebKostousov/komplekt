<script lang="ts">
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  let {
    title,
    subtitle = '',
    wide = false,
    onclose,
    children,
    footer,
  }: {
    title: string;
    subtitle?: string;
    wide?: boolean;
    onclose: () => void;
    children: Snippet;
    footer?: Snippet;
  } = $props();
  let dialog: HTMLDialogElement;
  onMount(() => {
    dialog.showModal();
    return () => dialog.close();
  });
</script>

<dialog
  bind:this={dialog}
  class:wide
  class="modal"
  aria-label={title}
  oncancel={(event) => {
    event.preventDefault();
    onclose();
  }}
>
  <div class="modal-head">
    <div>
      <h2>{title}</h2>
      {#if subtitle}<p>{subtitle}</p>{/if}
    </div>
    <button class="icon-button" type="button" aria-label="Закрыть окно" onclick={onclose}
      ><Icon name="close" /></button
    >
  </div>
  <div class="modal-body">{@render children()}</div>
  {#if footer}<div class="modal-foot">{@render footer()}</div>{/if}
</dialog>
