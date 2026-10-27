<script lang="ts">
  import { untrack } from 'svelte';
  import { onDestroy } from 'svelte';
  import { api, downloadPdf, problemFrom } from '../lib/api';
  import { buyerFieldLabel, count, date, decimal, money } from '../lib/format';
  import { clearQuoteKey, quoteKey } from '../lib/quoteKey';
  import type {
    ApiProblem,
    Buyer,
    Draft,
    Navigate,
    Product,
    QuoteLine,
    State,
    StateHandler,
  } from '../lib/types';
  import Icon from '../components/Icon.svelte';
  import Notice from '../components/Notice.svelte';
  import Problem from '../components/Problem.svelte';
  import Modal from '../components/Modal.svelte';
  import BuyerForm from '../components/BuyerForm.svelte';
  import QuoteRows from '../components/QuoteRows.svelte';
  import ProductChoice from '../components/ProductChoice.svelte';
  import QuoteSheet from '../components/QuoteSheet.svelte';
  import DiscountForm from '../components/DiscountForm.svelte';
  let {
    appState,
    requestId,
    onstate,
    onrequestchange,
    onnavigate,
    onpriceedit,
  }: {
    appState: State;
    requestId: string;
    onstate: StateHandler;
    onrequestchange: (id: string) => void;
    onnavigate: Navigate;
    onpriceedit: (product: Product) => void;
  } = $props();
  let request = $derived(
    appState.requests.find((item) => item.request_id === requestId) ?? appState.requests[0],
  );
  let quote = $state<Draft | null>(null);
  let loading = $state(false);
  let busy = $state(false);
  let buyerDirty = $state(false);
  let discountDirty = $state(false);
  let buyerSaving = $state(false);
  let discountSaving = $state(false);
  let savingForm = $derived(buyerSaving || discountSaving);
  let problem = $state<ApiProblem | null>(null);
  let selectedLine = $state<QuoteLine | null>(null);
  let showPreview = $state(false);
  let confirmIncomplete = $state(false);
  let created = $state('');
  let buyerSnapshot = $state<Buyer | null>(null);
  let discountSnapshot = $state<string | null>(null);
  let draftTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const id = request?.request_id;
    const revision = appState.revision;
    let cancelled = false;
    if (!id) {
      quote = null;
      return;
    }
    loading = true;
    if (untrack(() => quote?.request_id) !== id) quote = null;
    void api<{ revision: number; quote: Draft }>(`/requests/${encodeURIComponent(id)}/calculation`)
      .then((result) => {
        if (!cancelled && result.revision >= revision) quote = result.quote;
      })
      .catch((error) => {
        if (!cancelled) problem = problemFrom(error);
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });
    return () => {
      cancelled = true;
    };
  });
  onDestroy(() => clearTimeout(draftTimer));
  function rememberBuyer(value: Buyer) {
    buyerSnapshot = value;
    scheduleDraft();
  }
  function rememberDiscount(value: string) {
    discountSnapshot = value;
    scheduleDraft();
  }
  function scheduleDraft() {
    if (!draftChanged()) return;
    clearTimeout(draftTimer);
    draftTimer = setTimeout(() => void persistDraft(), 400);
  }
  function draftChanged(): boolean {
    if (!request || !buyerSnapshot || discountSnapshot === null) return false;
    return (
      JSON.stringify(buyerSnapshot) !== JSON.stringify(request.buyer_draft) ||
      discountSnapshot !== request.discount_draft
    );
  }
  async function persistDraft() {
    if (!request || !buyerSnapshot || discountSnapshot === null || !draftChanged()) return;
    const sentBuyer = buyerSnapshot;
    const sentDiscount = discountSnapshot;
    try {
      const next = await api<State>(`/requests/${encodeURIComponent(request.request_id)}/draft`, {
        method: 'PATCH',
        body: JSON.stringify({
          revision: appState.revision,
          buyer_draft: sentBuyer,
          discount_draft: sentDiscount,
        }),
      });
      const unchanged =
        JSON.stringify(buyerSnapshot) === JSON.stringify(sentBuyer) &&
        discountSnapshot === sentDiscount;
      if (unchanged) applyState(next);
    } catch (error) {
      if (!/conflict/i.test(problemFrom(error).code)) return;
      const fresh = await api<State>('/state').catch(() => null);
      if (fresh) applyState(fresh);
      if (draftChanged()) scheduleDraft();
    }
  }
  function applyState(next: State) {
    problem = null;
    onstate(next);
  }
  async function selection(lines: number[]) {
    if (!request) return;
    busy = true;
    problem = null;
    created = '';
    try {
      onstate(
        await api<State>(`/requests/${encodeURIComponent(request.request_id)}/selection`, {
          method: 'PUT',
          body: JSON.stringify({ revision: appState.revision, lines }),
        }),
      );
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
  function formReady(): boolean {
    if (savingForm) {
      problem = {
        code: 'saving',
        message: 'Подождите, пока сохранятся изменения в форме.',
        issues: [],
      };
      return false;
    }
    if (discountDirty) {
      problem = {
        code: 'unsaved_discount',
        message:
          'Примените скидку перед просмотром или сохранением КП. Нажмите «Применить» рядом с процентом.',
        issues: [],
      };
      return false;
    }
    if (buyerDirty) {
      problem = {
        code: 'unsaved',
        message: 'Сначала сохраните реквизиты покупателя. Кнопка находится под формой.',
        issues: [],
      };
      return false;
    }
    return true;
  }
  function preparePreview() {
    if (formReady()) showPreview = true;
  }
  function prepareExport() {
    if (!formReady()) return;
    if (!quote?.selected_count) {
      problem = {
        code: 'empty',
        message: 'Выберите хотя бы одну строку заявки для КП.',
        issues: [],
      };
      return;
    }
    if (!quote.is_complete) {
      confirmIncomplete = true;
      return;
    }
    void exportQuote(false);
  }
  async function exportQuote(allowIncomplete: boolean) {
    if (!request || busy) return;
    busy = true;
    problem = null;
    created = '';
    try {
      const result = await api<{ state: State; quote_id: string }>('/quotes', {
        method: 'POST',
        headers: { 'Idempotency-Key': quoteKey(appState.revision, request.request_id) },
        body: JSON.stringify({
          revision: appState.revision,
          request_id: request.request_id,
          allow_incomplete: allowIncomplete,
        }),
      });
      clearQuoteKey();
      confirmIncomplete = false;
      onstate(result.state);
      const saved = result.state.quotes.find((item) => item.id === result.quote_id);
      created = saved?.number ?? 'КП';
      await downloadPdf(result.quote_id, saved?.filename ?? 'kommercheskoe-predlozhenie.pdf');
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
</script>

<header class="page-heading">
  <div>
    <div class="eyebrow">От заявки к документу</div>
    <h1>Подготовка КП</h1>
    <p>Проверьте товары, укажите покупателя и сохраните предложение в PDF.</p>
  </div>
  {#if request}<label class="request-selector"
      ><span>Заявка</span><select
        value={request.request_id}
        onchange={(event) => onrequestchange(event.currentTarget.value)}
        >{#each appState.requests as item}<option value={item.request_id}>{item.request_id}</option
          >{/each}</select
      ></label
    >{/if}
</header>
{#if !request}
  <section class="panel empty-state">
    <span class="empty-icon"><Icon name="quote" size={36} /></span>
    <h2>Для КП нужна заявка</h2>
    <p>
      Загрузите список товаров покупателя в разделе «Заявки». После этого здесь появятся строки для
      расчёта.
    </p>
    <button class="button primary" onclick={() => onnavigate('requests')}
      >К загрузке заявки<Icon name="arrow" size={18} /></button
    >
  </section>
{:else}
  {#if created}<Notice tone="success" title={`${created} сохранено`}
      ><p>
        PDF подготовлен к скачиванию. Документ также доступен в истории: он не изменится после
        правки прайса.
      </p>
      <button class="text-button" onclick={() => onnavigate('history')}
        >Открыть историю КП<Icon name="arrow" size={15} /></button
      ></Notice
    >{/if}
  {#if !appState.catalog}<Notice tone="warning" title="Прайс ещё не загружен"
      ><p>Сохраните товары и цены в разделе «Прайс». Пока позиции заявки останутся без расчёта.</p>
      <button class="text-button" onclick={() => onnavigate('price')}
        >Загрузить прайс<Icon name="arrow" size={15} /></button
      ></Notice
    >{/if}
  <Problem {problem} />
  <div class="quote-layout">
    <div class="quote-main">
      <section class="panel quote-lines-panel">
        <div class="panel-heading">
          <div class="heading-icon"><Icon name="box" /></div>
          <div>
            <h2>Состав предложения</h2>
            <p>Галочками отметьте строки заявки, которые войдут в КП.</p>
          </div>
          <span class="tag neutral">01</span>
        </div>
        {#if quote}<QuoteRows
            {request}
            {quote}
            busy={busy || loading}
            onselection={selection}
            onresolve={(line) => (selectedLine = line)}
            {onpriceedit}
          />{:else}<div class="loading-section">
            <span class="spinner"></span>Проверяем товары и цены…
          </div>{/if}
        {#if quote?.unresolved_count}<div class="unresolved-note">
            <Icon name="warning" size={17} /><span
              >{count(quote.unresolved_count)}
              {quote.unresolved_count === 1 ? 'нуждается' : 'нуждаются'} в уточнении. Нажмите на действие
              в колонке «Проверка».</span
            >
          </div>{/if}
      </section>
      {#key request.request_id}<BuyerForm
          {request}
          {appState}
          onstate={applyState}
          ondirty={(value) => (buyerDirty = value)}
          onbusy={(value) => (buyerSaving = value)}
          ondraft={rememberBuyer}
        />{/key}
      <section class="panel fixed-terms">
        <div class="panel-heading">
          <div class="heading-icon"><Icon name="file" /></div>
          <div>
            <h2>Что будет в документе</h2>
            <p>Продавец, предмет предложения и условия заданы для учебного примера.</p>
          </div>
          <span class="tag neutral">03</span>
        </div>
        <dl>
          <div>
            <dt>Продавец</dt>
            <dd>{appState.seller.company_name}<small>Компания и реквизиты вымышлены</small></dd>
          </div>
          <div>
            <dt>Предмет</dt>
            <dd>Поставка промышленных компонентов по заявке покупателя</dd>
          </div>
          <div>
            <dt>Условия</dt>
            <dd>
              100% предоплата после согласования заказа. Срок и способ доставки согласуются
              отдельно. Предложение действует 10 календарных дней.
            </dd>
          </div>
        </dl>
      </section>
    </div>
    <aside class="quote-summary">
      <div class="summary-label">
        <span class="live-dot"></span>Текущий расчёт{#if loading}<span class="spinner small-spinner"
          ></span>{/if}
      </div>
      <h2>{quote?.calculation_complete ? 'Итого по КП' : 'Подытог'}</h2>
      <div class="summary-amount">
        {quote?.confirmed_count
          ? money(quote.subtotal_with_vat)
          : 'Не рассчитан'}{#if quote?.confirmed_count}<span>₽</span>{/if}
      </div>
      <p class="summary-caption">
        {quote?.calculation_complete
          ? 'Все выбранные позиции рассчитаны'
          : 'Только подтверждённые позиции'}
      </p>
      <dl class="summary-lines">
        <div>
          <dt>В том числе НДС 20%</dt>
          <dd>{quote?.confirmed_count ? money(quote.vat_amount, true) : '—'}</dd>
        </div>
        <div>
          <dt>Рассчитано</dt>
          <dd>{quote?.confirmed_count ?? 0} из {request.selected_lines.length}</dd>
        </div>
        {#if quote?.excluded_count}<div>
            <dt>Исключено вручную</dt>
            <dd>{quote.excluded_count}</dd>
          </div>{/if}
        <div>
          <dt>Скидка</dt>
          <dd>{decimal(quote?.discount_percent ?? request.discount_percent)}%</dd>
        </div>
      </dl>
      {#key request.request_id}<DiscountForm
          {request}
          {appState}
          onstate={applyState}
          ondirty={(value) => (discountDirty = value)}
          onbusy={(value) => (discountSaving = value)}
          ondraft={rememberDiscount}
        />{/key}
      {#if quote && !quote.is_complete}<div class="summary-warning">
          <Icon name="warning" size={17} />
          <p>
            {quote.unresolved_count
              ? 'В PDF останутся строки без расчёта. Документ будет помечен как черновик.'
              : 'Для готового КП заполните название, ИНН и адрес покупателя.'}
          </p>
        </div>{/if}
      <button
        class="button primary full"
        disabled={busy || loading || savingForm || !quote || !request.selected_lines.length}
        onclick={prepareExport}
        ><Icon name="download" size={18} />{busy
          ? 'Готовим документ…'
          : 'Сохранить КП в PDF'}</button
      ><button
        class="button ghost full"
        disabled={!quote || loading || savingForm}
        onclick={preparePreview}><Icon name="eye" size={18} />Посмотреть содержание</button
      >
      <p class="summary-footnote">
        КП сохранится в истории.<br />Ничего не отправляется покупателю.
      </p>
      <div class="source-summary">
        <span>Источники</span>
        <p><Icon name="file" size={14} />{request.filename}</p>
        <p><Icon name="file" size={14} />{appState.catalog?.filename ?? 'Прайс не загружен'}</p>
        {#if appState.catalog}<small>Прайс от {date(appState.catalog.uploaded_at, true)}</small
          >{/if}
      </div>
    </aside>
  </div>
{/if}
{#if selectedLine && request}<ProductChoice
    line={selectedLine}
    {request}
    {appState}
    {onstate}
    onclose={() => (selectedLine = null)}
  />{/if}
{#if showPreview && quote}<Modal
    title="Содержание предложения"
    subtitle="Проверьте данные перед сохранением PDF."
    wide
    onclose={() => (showPreview = false)}
    ><QuoteSheet {quote} seller={appState.seller} />{#snippet footer()}<button
        class="button secondary"
        onclick={() => (showPreview = false)}>Вернуться к расчёту</button
      ><button
        class="button primary"
        disabled={busy || loading}
        onclick={() => {
          showPreview = false;
          prepareExport();
        }}><Icon name="download" size={18} />Сохранить КП в PDF</button
      >{/snippet}</Modal
  >{/if}
{#if confirmIncomplete && quote}<Modal
    title="Сохранить неполный черновик?"
    subtitle="В документе будет явно указано, какие данные ещё нужны."
    onclose={() => {
      if (!busy) confirmIncomplete = false;
    }}
    ><Notice tone="warning" title="Проверьте, что остаётся незаполненным"
      ><ul class="issue-list">
        {#if quote.unresolved_count}<li>
            Без расчёта: {count(quote.unresolved_count)}. Их стоимость не включена в подытог.
          </li>{/if}{#if quote.missing_buyer_fields.length}<li>
            Реквизиты покупателя: {quote.missing_buyer_fields.map(buyerFieldLabel).join(', ')}.
          </li>{/if}
      </ul></Notice
    >
    <p class="confirmation-total">
      {quote.confirmed_count
        ? `Подытог рассчитанных позиций — ${money(quote.subtotal_with_vat, true)}.`
        : 'Нет ни одной рассчитанной позиции. Сумма КП не определена.'}
    </p>
    <p class="muted">
      Можно вернуться и дополнить данные. Если сохраните сейчас, PDF останется черновиком даже после
      дальнейших правок.
    </p>
    <Problem {problem} />{#snippet footer()}<button
        class="button secondary"
        disabled={busy}
        onclick={() => (confirmIncomplete = false)}>Дополнить данные</button
      ><button class="button primary" disabled={busy} onclick={() => exportQuote(true)}
        >{busy ? 'Готовим…' : 'Сохранить черновик'}</button
      >{/snippet}</Modal
  >{/if}
