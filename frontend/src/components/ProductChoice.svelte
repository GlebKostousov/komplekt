<script lang="ts">
  import { untrack } from 'svelte';
  import { api, problemFrom } from '../lib/api';
  import { money } from '../lib/format';
  import type { ApiProblem, QuoteLine, RequestRecord, State, StateHandler } from '../lib/types';
  import Modal from './Modal.svelte';
  import Notice from './Notice.svelte';
  import Problem from './Problem.svelte';
  let {
    line,
    request,
    appState,
    onstate,
    onclose,
  }: {
    line: QuoteLine;
    request: RequestRecord;
    appState: State;
    onstate: StateHandler;
    onclose: () => void;
  } = $props();
  let selected = $state(untrack(() => request.choices[String(line.request.line)] ?? ''));
  let allProducts = $state(untrack(() => line.status === 'not_found' || line.manually_selected));
  let busy = $state(false);
  let problem = $state<ApiProblem | null>(null);
  let choices = $derived(allProducts ? (appState.catalog?.products ?? []) : line.candidates);
  let product = $derived(appState.catalog?.products.find((item) => item.id === selected));
  async function save(value: string | null) {
    busy = true;
    problem = null;
    try {
      onstate(
        await api<State>(
          `/requests/${encodeURIComponent(request.request_id)}/choices/${line.request.line}`,
          {
            method: 'PUT',
            body: JSON.stringify({ revision: appState.revision, product_id: value }),
          },
        ),
      );
      onclose();
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title={line.status === 'not_found'
    ? 'Товар не найден в прайсе'
    : 'Выберите товар для этой строки'}
  subtitle={`Строка ${line.request.line} · ${line.request.name} · ${line.request.quantity} шт.`}
  onclose={() => {
    if (!busy) onclose();
  }}
>
  {#if line.status === 'not_found'}<Notice
      tone="warning"
      title={line.request.sku
        ? `Артикула ${line.request.sku} нет в прайсе`
        : 'Нет подходящего названия'}
      ><p>
        Можно оставить строку без расчёта и обновить прайс позже. Если согласована замена, выберите
        её ниже. Исходная строка заявки сохранится.
      </p></Notice
    >{:else}<p class="muted">
      Уточните характеристики у покупателя и выберите нужный вариант. До вашего выбора эта строка не
      входит в расчёт.
    </p>{/if}
  <label class="field"
    ><span>Товар из текущего прайса</span><select
      bind:value={selected}
      disabled={!choices.length || busy}
      ><option value="">Выберите товар</option>{#each choices as item}<option value={item.id}
          >{item.sku} · {item.name} · {item.price === null
            ? 'цены нет'
            : `${money(item.price)} ₽ / ${item.unit}`}</option
        >{/each}</select
    ></label
  >
  {#if !allProducts && appState.catalog?.products.length}<button
      class="text-button"
      onclick={() => (allProducts = true)}>Показать весь прайс</button
    >{/if}
  {#if product}<div class="selected-product-summary">
      <strong>{product.name}</strong>
      <p>
        {product.sku} · {product.unit === 'упак'
          ? `Упаковка, ${product.pack_size} шт.`
          : 'Продажа поштучно'}
      </p>
      <p>
        {product.price === null
          ? 'Цена не указана — после выбора её нужно будет уточнить.'
          : `${money(product.price, true)} / ${product.unit}, ${product.price_basis === 'net' ? 'без НДС' : 'НДС включён'}`}
      </p>
    </div>{/if}
  {#if !choices.length}<Notice title="Сначала добавьте товары"
      ><p>Загрузите прайс в разделе «Прайс». До этого строка останется без расчёта.</p></Notice
    >{/if}
  {#if line.manually_selected}<button class="text-button" disabled={busy} onclick={() => save(null)}
      >Убрать мой выбор и повторить подбор</button
    >{/if}
  <Problem {problem} />
  {#snippet footer()}<button class="button secondary" disabled={busy} onclick={onclose}
      >Заполнить позже</button
    ><button class="button primary" disabled={!selected || busy} onclick={() => save(selected)}
      >{busy
        ? 'Сохраняем…'
        : line.status === 'not_found'
          ? 'Подтвердить замену'
          : 'Сохранить выбор'}</button
    >{/snippet}
</Modal>
