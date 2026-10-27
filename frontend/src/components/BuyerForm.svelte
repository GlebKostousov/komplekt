<script lang="ts">
  import { untrack } from 'svelte';
  import { api, problemFrom } from '../lib/api';
  import type { ApiProblem, Buyer, RequestRecord, State, StateHandler } from '../lib/types';
  import { buyerLabels } from '../lib/format';
  import Icon from './Icon.svelte';
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
    ondraft: (value: Buyer) => void;
  } = $props();
  let buyer = $state<Buyer>(untrack(() => ({ ...request.buyer_draft })));
  let busy = $state(false);
  let saved = $state(false);
  let problem = $state<ApiProblem | null>(null);
  let dirty = $derived(JSON.stringify(buyer) !== JSON.stringify(request.buyer));
  $effect(() => {
    ondraft(buyer);
  });
  $effect(() => {
    ondirty(dirty);
  });
  $effect(() => {
    onbusy(busy);
  });
  type BuyerField = {
    key: keyof Buyer;
    placeholder: string;
    max: number;
    mode?: 'numeric' | 'email' | 'tel';
  };
  const basic: BuyerField[] = [
    { key: 'company_name', placeholder: 'Например, ООО «Северный проект»', max: 200 },
    { key: 'inn', placeholder: '10 цифр для ООО, 12 — для ИП', max: 12, mode: 'numeric' },
    { key: 'address', placeholder: 'Город, улица, дом, офис', max: 350 },
  ];
  const additional: BuyerField[] = [
    { key: 'kpp', placeholder: '9 цифр, только для организации', max: 9, mode: 'numeric' },
    { key: 'ogrn', placeholder: '13 или 15 цифр', max: 15, mode: 'numeric' },
    { key: 'contact_name', placeholder: 'Имя и фамилия', max: 150 },
    { key: 'phone', placeholder: '+7 900 000-00-00', max: 30, mode: 'tel' },
    { key: 'email', placeholder: 'name@example.ru', max: 254, mode: 'email' },
    { key: 'bank_name', placeholder: 'Полное название банка', max: 200 },
    { key: 'bik', placeholder: '9 цифр', max: 9, mode: 'numeric' },
    { key: 'account', placeholder: '20 цифр', max: 20, mode: 'numeric' },
    { key: 'correspondent_account', placeholder: '20 цифр', max: 20, mode: 'numeric' },
  ];
  function fieldIssue(key: string): string | undefined {
    return problem?.issues.find((issue) => issue.field === key || issue.field === `buyer.${key}`)
      ?.message;
  }
  function fillExample() {
    buyer = {
      company_name: 'ООО «Северный завод Демо»',
      inn: '9900000000',
      kpp: '990001001',
      ogrn: '',
      address: 'Учебный город, улица Примеров, дом 1',
      contact_name: 'Отдел закупок',
      email: 'zakupki@example.com',
      phone: '',
      bank_name: '',
      bik: '',
      account: '',
      correspondent_account: '',
    };
    problem = null;
    saved = false;
  }
  async function save() {
    busy = true;
    saved = false;
    problem = null;
    try {
      const next = await api<State>(`/requests/${encodeURIComponent(request.request_id)}/buyer`, {
        method: 'PATCH',
        body: JSON.stringify({ revision: appState.revision, buyer }),
      });
      const stored = next.requests.find((item) => item.request_id === request.request_id);
      if (stored) buyer = { ...stored.buyer };
      onstate(next);
      saved = true;
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="panel buyer-panel" aria-labelledby="buyer-heading">
  <div class="panel-heading">
    <div class="heading-icon"><Icon name="building" /></div>
    <div>
      <h2 id="buyer-heading">Покупатель</h2>
      <p>Реквизиты попадут в документ. Используйте вымышленные данные.</p>
    </div>
    <span class="tag neutral">02</span>
  </div>
  <form
    novalidate
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    <div class="sample-buyer">
      <span>Нет данных под рукой? Можно проверить на вымышленном покупателе.</span><button
        type="button"
        class="text-button"
        onclick={fillExample}>Заполнить примером</button
      >
    </div>
    <div class="form-grid">
      {#each basic as field}{@render buyerField(field, true)}{/each}
    </div>
    <details class="additional-fields">
      <summary
        >Контактные и банковские реквизиты <span>необязательно</span><Icon
          name="chevronDown"
          size={17}
        /></summary
      >
      <div class="form-grid">
        {#each additional as field}{@render buyerField(field, false)}{/each}
      </div>
    </details>
    <Problem {problem} />
    <div class="form-actions">
      <span class="save-hint" aria-live="polite"
        >{#if dirty}Есть несохранённые изменения{:else if saved}<Icon
            name="check"
            size={16}
          />Реквизиты сохранены{:else}Пустые поля можно заполнить позже{/if}</span
      ><button type="submit" class="button secondary small" disabled={busy || !dirty}
        >{busy ? 'Сохраняем…' : 'Сохранить реквизиты'}</button
      >
    </div>
  </form>
</section>

{#snippet buyerField(field: BuyerField, required: boolean)}
  <div class="field" class:span-two={field.key === 'company_name'}>
    <label for={`buyer-${field.key}`}>
      <span
        >{field.key === 'company_name'
          ? 'Название организации или ИП'
          : buyerLabels[field.key]}{#if required}{' '}<em>для готового КП</em>{/if}</span
      >
    </label>
    <input
      id={`buyer-${field.key}`}
      type="text"
      inputmode={field.mode}
      maxlength={field.max}
      bind:value={buyer[field.key]}
      placeholder={field.placeholder}
      aria-invalid={Boolean(fieldIssue(field.key))}
      aria-describedby={fieldIssue(field.key) ? `buyer-${field.key}-error` : undefined}
    />
    {#if fieldIssue(field.key)}
      <small id={`buyer-${field.key}-error`} class="field-error">{fieldIssue(field.key)}</small>
    {/if}
  </div>
{/snippet}
