<script lang="ts">
  import { untrack } from 'svelte';
  import { api, problemFrom } from '../lib/api';
  import type { ApiProblem, RequestRecord, State, StateHandler } from '../lib/types';
  import Problem from './Problem.svelte';
  let {
    request,
    appState,
    onstate,
    ondirty,
    onbusy,
    ondraft,
  }: {
    request: RequestRecord;
    appState: State;
    onstate: StateHandler;
    ondirty: (value: boolean) => void;
    onbusy: (value: boolean) => void;
    ondraft: (value: string) => void;
  } = $props();
  let discount = $state(untrack(() => request.discount_draft.replaceAll('.', ',')));
  let busy = $state(false);
  let problem = $state<ApiProblem | null>(null);
  let dirty = $derived(!samePercent(discount, request.discount_percent));
  $effect(() => {
    ondraft(discount);
  });
  $effect(() => {
    ondirty(dirty);
  });
  $effect(() => {
    onbusy(busy);
  });
  function samePercent(raw: string, stored: string): boolean {
    return normalizePercent(raw) === normalizePercent(stored);
  }
  function normalizePercent(value: string): string {
    const text = value.trim().replace(',', '.');
    if (!/^\d+(?:\.\d+)?$/.test(text)) return text;
    const [whole, fraction = ''] = text.split('.');
    const trimmedWhole = whole.replace(/^0+(?=\d)/, '');
    const trimmedFraction = fraction.replace(/0+$/, '');
    return trimmedFraction ? `${trimmedWhole}.${trimmedFraction}` : trimmedWhole;
  }
  async function save() {
    busy = true;
    problem = null;
    try {
      const next = await api<State>(
        `/requests/${encodeURIComponent(request.request_id)}/discount`,
        {
          method: 'PATCH',
          body: JSON.stringify({ revision: appState.revision, discount_percent: discount }),
        },
      );
      const stored = next.requests.find((item) => item.request_id === request.request_id);
      if (stored) discount = stored.discount_percent.replace('.', ',');
      onstate(next);
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
</script>

<form
  class="discount-form"
  onsubmit={(event) => {
    event.preventDefault();
    void save();
  }}
>
  <label for="discount-input">Скидка на каждую позицию</label>
  <div>
    <span class="number-suffix"
      ><input
        id="discount-input"
        type="text"
        inputmode="decimal"
        maxlength="16"
        bind:value={discount}
        aria-label="Скидка, процентов"
      /><span>%</span></span
    ><button class="button secondary small" type="submit" disabled={busy || !dirty}
      >{busy ? '…' : 'Применить'}</button
    >
  </div>
</form>
{#if dirty}<p class="discount-dirty-note">Нажмите «Применить», чтобы пересчитать сумму.</p>{/if}
<Problem {problem} />
