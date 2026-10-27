<script lang="ts">
  import { untrack } from 'svelte';
  import { api, problemFrom } from '../lib/api';
  import type { Product, State, StateHandler, ApiProblem } from '../lib/types';
  import Modal from './Modal.svelte';
  import Notice from './Notice.svelte';
  import Problem from './Problem.svelte';
  let {
    product,
    appState,
    onstate,
    onclose,
    onsaved,
  }: {
    product: Product;
    appState: State;
    onstate: StateHandler;
    onclose: () => void;
    onsaved: () => void;
  } = $props();
  let price = $state(untrack(() => product.price?.replace('.', ',') ?? ''));
  let source = $state('Уточнено вручную');
  let busy = $state(false);
  let problem = $state<ApiProblem | null>(null);
  async function save() {
    busy = true;
    problem = null;
    try {
      onstate(
        await api<State>(`/products/${encodeURIComponent(product.id)}`, {
          method: 'PATCH',
          body: JSON.stringify({
            revision: appState.revision,
            price: price.trim() || null,
            source: source.trim(),
          }),
        }),
      );
      onsaved();
      onclose();
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title={product.price === null ? 'Уточнить цену' : 'Изменить цену'}
  subtitle={`${product.sku} · ${product.name}`}
  onclose={() => {
    if (!busy) onclose();
  }}
>
  <form
    id="price-form"
    onsubmit={(event) => {
      event.preventDefault();
      void save();
    }}
  >
    <div class="price-unit-note">
      <span
        >Цена за {product.unit === 'упак' ? `упаковку из ${product.pack_size} шт.` : 'штуку'}</span
      ><span class="tag neutral"
        >{product.price_basis === 'gross' ? 'НДС уже включён' : 'Без НДС'}</span
      >
    </div>
    <label class="field"
      ><span>Цена, ₽</span><input
        inputmode="decimal"
        maxlength="18"
        bind:value={price}
        placeholder="Например, 1250,50"
        autocomplete="off"
      /><small>До двух знаков после запятой. Без знака ₽ и пробелов.</small></label
    >
    <label class="field"
      ><span>Откуда взята цена</span><input
        type="text"
        maxlength="500"
        bind:value={source}
        placeholder="Например, прайс поставщика от 27.10"
        required
      /><small>Источник сохранится рядом с ценой и в расчёте.</small></label
    >
    <Notice title="Цена изменится в текущем прайсе"
      ><p>
        Она будет использоваться во всех заявках. Сохранённые КП останутся прежними. Пустое поле
        означает, что цена пока неизвестна.
      </p></Notice
    >
    <Problem {problem} />
  </form>
  {#snippet footer()}<button class="button secondary" disabled={busy} onclick={onclose}
      >Заполнить позже</button
    ><button class="button primary" type="submit" form="price-form" disabled={busy}
      >{busy ? 'Сохраняем…' : 'Сохранить цену'}</button
    >{/snippet}
</Modal>
