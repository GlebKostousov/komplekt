<script lang="ts">
  import { api, downloadPdf, problemFrom } from '../lib/api';
  import { count, date, money } from '../lib/format';
  import type { ApiProblem, Navigate, QuoteSummary, SavedQuote, State } from '../lib/types';
  import Icon from '../components/Icon.svelte';
  import Notice from '../components/Notice.svelte';
  import Problem from '../components/Problem.svelte';
  import Modal from '../components/Modal.svelte';
  import QuoteSheet from '../components/QuoteSheet.svelte';
  let { appState, onnavigate }: { appState: State; onnavigate: Navigate } = $props();
  let search = $state('');
  let selected = $state<SavedQuote | null>(null);
  let busyId = $state('');
  let problem = $state<ApiProblem | null>(null);
  let filtered = $derived(
    appState.quotes.filter((item) =>
      `${item.number} ${item.request_id} ${item.buyer_name}`
        .toLocaleLowerCase('ru')
        .includes(search.toLocaleLowerCase('ru').trim()),
    ),
  );
  async function download(item: QuoteSummary) {
    busyId = item.id;
    problem = null;
    try {
      await downloadPdf(item.id, item.filename);
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busyId = '';
    }
  }
  async function inspect(id: string) {
    busyId = id;
    problem = null;
    try {
      selected = await api<SavedQuote>(`/quotes/${encodeURIComponent(id)}`);
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busyId = '';
    }
  }
</script>

<header class="page-heading">
  <div>
    <div class="eyebrow">Сохранённые документы</div>
    <h1>История КП</h1>
    <p>Скачайте предложение повторно или проверьте, какие данные в него вошли.</p>
  </div>
</header>
<Problem {problem} />
{#if !appState.quotes.length}<section class="panel empty-state">
    <span class="empty-icon"><Icon name="history" size={36} /></span>
    <h2>Здесь будут готовые документы</h2>
    <p>
      Когда вы сохраните первое КП в PDF, оно появится в истории. Цены и реквизиты в сохранённом
      документе больше не изменятся.
    </p>
    <button class="button primary" onclick={() => onnavigate('quote')}
      >Подготовить КП<Icon name="arrow" size={18} /></button
    >
  </section>{:else}
  <Notice title="Каждое КП хранится таким, каким вы его сохранили"
    ><p>
      Правки цен, новая заявка и замена прайса не меняют выпущенные документы. Для актуального
      расчёта создайте новое КП.
    </p></Notice
  >
  <section class="panel">
    <div class="catalog-head">
      <div><h2>Документы <span class="count-label">{appState.quotes.length}</span></h2></div>
      <label class="search-field"
        ><Icon name="search" size={18} /><input
          type="search"
          bind:value={search}
          placeholder="Номер КП, заявка или покупатель"
          aria-label="Поиск в истории КП"
        /></label
      >
    </div>
    <div class="table-scroll">
      <table class="history-table">
        <thead
          ><tr
            ><th>Документ</th><th>Покупатель / заявка</th><th>Состояние</th><th class="numeric"
              >Сумма с НДС, ₽</th
            ><th><span class="visually-hidden">Действия с документом</span></th></tr
          ></thead
        ><tbody
          >{#each filtered as item}<tr
              ><td
                ><button
                  class="document-name"
                  disabled={Boolean(busyId)}
                  onclick={() => inspect(item.id)}
                  ><span class="pdf-file">PDF</span><span
                    ><strong>{item.number}</strong><small>{date(item.created_at, true)}</small
                    ></span
                  ></button
                ></td
              ><td
                ><strong>{item.buyer_name || 'Покупатель не указан'}</strong><span
                  class="cell-subtitle">{item.request_id} · {count(item.selected_count)}</span
                ></td
              ><td
                ><span
                  class="tag"
                  class:success={item.is_complete}
                  class:warning={!item.is_complete}>{item.is_complete ? 'Готово' : 'Черновик'}</span
                ></td
              ><td class="numeric"
                ><strong
                  >{item.selected_count > item.unresolved_count
                    ? money(item.subtotal_with_vat)
                    : 'Не рассчитана'}</strong
                >{#if item.unresolved_count}<span class="cell-subtitle">Подытог</span>{/if}</td
              ><td
                ><div class="row-actions">
                  <button
                    class="icon-button"
                    disabled={Boolean(busyId)}
                    onclick={() => inspect(item.id)}
                    aria-label={`Посмотреть ${item.number}`}><Icon name="eye" size={18} /></button
                  ><button
                    class="button secondary small"
                    disabled={Boolean(busyId)}
                    onclick={() => download(item)}
                    ><Icon name="download" size={16} />{busyId === item.id
                      ? 'Подождите…'
                      : 'Скачать'}</button
                  >
                </div></td
              ></tr
            >{/each}</tbody
        >
      </table>
    </div>
    {#if !filtered.length}<div class="table-empty">
        <Icon name="search" size={26} />
        <h3>Документов не найдено</h3>
        <p>Попробуйте другой номер или название покупателя.</p>
      </div>{/if}
  </section>
{/if}
{#if selected}<Modal
    title={selected.number}
    subtitle={`Сохранено ${date(selected.created_at, true)}. Эти данные больше не меняются.`}
    wide
    onclose={() => (selected = null)}
    ><QuoteSheet
      quote={selected.quote}
      seller={selected.seller}
      number={selected.number}
      createdAt={selected.created_at}
    />
    <details class="source-details">
      <summary>Исходные файлы и проверка документа</summary>
      <p>Заявка: <strong>{selected.quote.request_source.name}</strong></p>
      <code>{selected.quote.request_source.sha256}</code>{#if selected.quote.price_source}<p>
          Прайс: <strong>{selected.quote.price_source.name}</strong>
        </p>
        <code>{selected.quote.price_source.sha256}</code>{/if}
      <p class="footnote">Отпечатки позволяют проверить, из каких именно файлов получены данные.</p>
    </details>
    {#snippet footer()}<a
        class="button secondary"
        target="_blank"
        rel="noopener"
        href={`/api/quotes/${encodeURIComponent(selected?.id ?? '')}/pdf?inline=true`}
        ><Icon name="eye" size={18} />Открыть PDF</a
      ><button
        class="button primary"
        onclick={() => {
          const item = appState.quotes.find((value) => value.id === selected?.id);
          if (item) void download(item);
        }}><Icon name="download" size={18} />Скачать PDF</button
      >{/snippet}</Modal
  >{/if}
