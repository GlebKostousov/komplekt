<script lang="ts">
  import type { ImportKind, Product, State, StateHandler } from '../lib/types';
  import { count, date, money } from '../lib/format';
  import Icon from '../components/Icon.svelte';
  import UploadPanel from '../components/UploadPanel.svelte';
  import Notice from '../components/Notice.svelte';
  let {
    appState,
    onstate,
    onguide,
    onpriceedit,
  }: {
    appState: State;
    onstate: StateHandler;
    onguide: (kind: ImportKind) => void;
    onpriceedit: (product: Product) => void;
  } = $props();
  let search = $state('');
  let missingOnly = $state(false);
  let imported = $state(false);
  let missing = $derived(appState.catalog?.products.filter((item) => item.price === null) ?? []);
  let filtered = $derived(
    (appState.catalog?.products ?? []).filter(
      (item) =>
        (!missingOnly || item.price === null) &&
        `${item.sku} ${item.name}`
          .toLocaleLowerCase('ru')
          .includes(search.toLocaleLowerCase('ru').trim()),
    ),
  );
</script>

<header class="page-heading">
  <div>
    <div class="eyebrow">Товары и цены</div>
    <h1>Прайс</h1>
    <p>Актуальные цены для расчёта. Правки здесь применяются ко всем заявкам.</p>
  </div>
  <button class="button ghost" onclick={() => onguide('price')}
    ><Icon name="book" size={18} />Как подготовить файл</button
  >
</header>
{#if !appState.catalog}
  <div class="onboarding-layout">
    <section class="panel first-upload">
      <div class="section-kicker"><span class="step-number">2</span>Прайс поставщика</div>
      <h2>Добавьте товары и цены</h2>
      <p class="section-description">
        Цена указывается за единицу продажи: штуку или упаковку. Неизвестную цену оставьте пустой —
        её можно внести после загрузки.
      </p>
      <UploadPanel
        kind="price"
        {appState}
        {onstate}
        {onguide}
        oncommitted={() => (imported = true)}
      />
    </section>
    <aside class="start-aside price-aside">
      <span class="large-outline-icon"><Icon name="box" size={46} stroke={1.2} /></span>
      <h3>Упаковки посчитаем правильно</h3>
      <p>
        Например, покупателю нужны 20 штук, а в упаковке — 10. В КП будет 2 упаковки по цене из
        прайса.
      </p>
      <div class="package-example">
        <span>20 <small>штук</small></span><Icon name="arrow" size={22} /><span
          >2 <small>упаковки</small></span
        >
      </div>
      <p class="footnote">
        Если количество не делится на размер упаковки, приложение попросит его уточнить.
      </p>
    </aside>
  </div>
{:else}
  {#if missing.length}
    <Notice
      tone="warning"
      title={imported
        ? 'Прайс сохранён. Теперь можно уточнить цены'
        : 'В прайсе есть товары без цены'}
      ><p>
        У {count(missing.length, ['товара', 'товаров', 'товаров'])} цена пока не указана. Заполните её
        сейчас или позже, при подготовке КП.
      </p>
      <div class="notice-actions">
        <button class="button warning-button small" onclick={() => onpriceedit(missing[0])}
          >Уточнить цену</button
        ><button class="text-button" onclick={() => (missingOnly = true)}>Показать без цены</button>
      </div></Notice
    >
  {:else if imported}<Notice tone="success" title="Прайс сохранён"
      ><p>Все товары имеют цену. Можно перейти к подготовке КП.</p></Notice
    >{/if}
  <details class="panel import-disclosure">
    <summary
      ><div>
        <Icon name="upload" size={19} /><strong>Загрузить новый прайс</strong><span
          >Полностью заменит текущий</span
        >
      </div>
      <Icon name="chevronDown" size={18} /></summary
    ><UploadPanel
      compact
      kind="price"
      {appState}
      {onstate}
      {onguide}
      oncommitted={() => (imported = true)}
    />
  </details>
  <section class="panel catalog-panel">
    <div class="catalog-head">
      <div>
        <h2>Товары <span class="count-label">{appState.catalog.products.length}</span></h2>
        <p>{appState.catalog.filename} · обновлён {date(appState.catalog.uploaded_at, true)}</p>
      </div>
      <label class="search-field"
        ><Icon name="search" size={18} /><input
          type="search"
          bind:value={search}
          placeholder="Название или артикул"
          aria-label="Поиск товара в прайсе"
        /></label
      >
    </div>
    <div class="table-tabs">
      <button class:active={!missingOnly} onclick={() => (missingOnly = false)}>Все товары</button
      ><button class:active={missingOnly} onclick={() => (missingOnly = true)}
        >Без цены <span>{missing.length}</span></button
      >
    </div>
    <div class="table-scroll">
      <table class="catalog-table">
        <thead
          ><tr
            ><th>Товар</th><th>Продажа</th><th class="numeric">Цена, ₽</th><th>НДС</th><th
              >Источник</th
            ><th><span class="visually-hidden">Изменение цены</span></th></tr
          ></thead
        ><tbody
          >{#each filtered as product}<tr class:needs-attention={product.price === null}
              ><td
                ><strong>{product.name}</strong><span class="cell-subtitle mono">{product.sku}</span
                ></td
              ><td
                >{product.unit === 'упак' ? 'Упаковка' : 'Штука'}<span class="cell-subtitle"
                  >{product.pack_size} шт.</span
                ></td
              ><td class="numeric price-cell"
                >{#if product.price === null}<span class="tag warning">Не указана</span
                  >{:else}<strong>{money(product.price)}</strong>{/if}</td
              ><td
                ><span class="tax-label"
                  >{product.price_basis === 'gross' ? 'Включён' : 'Сверху'}</span
                ><span class="cell-subtitle">20%</span></td
              ><td class="source-cell">{product.source}</td><td
                ><button
                  class="button small"
                  class:secondary={product.price === null}
                  class:ghost={product.price !== null}
                  onclick={() => onpriceedit(product)}
                  aria-label={`${product.price === null ? 'Указать' : 'Изменить'} цену: ${product.name}`}
                  ><Icon name="edit" size={16} />{product.price === null
                    ? 'Указать цену'
                    : 'Изменить'}</button
                ></td
              ></tr
            >{/each}</tbody
        >
      </table>
    </div>
    {#if !filtered.length}<div class="table-empty">
        <Icon name="search" size={26} />
        <h3>{missingOnly && !search ? 'Все цены заполнены' : 'Товаров не найдено'}</h3>
        <p>
          {missingOnly && !search
            ? 'Можно готовить коммерческое предложение.'
            : 'Попробуйте другое название или артикул.'}
        </p>
      </div>{/if}
    <div class="panel-footer">
      <Icon name="info" size={16} />
      <p>
        Цена до скидки. НДС «Включён» — повторно не прибавляем. НДС «Сверху» — добавляем после
        скидки.
      </p>
    </div>
  </section>
{/if}
<div class="roadmap-note">
  <Icon name="link" size={17} />
  <p>
    В этой версии загружаем CSV. Прямое подключение к источнику, версии прайса, остатки и история
    цен — следующий этап.
  </p>
</div>
