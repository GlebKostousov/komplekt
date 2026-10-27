<script lang="ts">
  import type { ImportKind, Navigate, State, StateHandler } from '../lib/types';
  import { count, date } from '../lib/format';
  import Icon from '../components/Icon.svelte';
  import UploadPanel from '../components/UploadPanel.svelte';
  import Notice from '../components/Notice.svelte';
  let {
    appState,
    onstate,
    onnavigate,
    onguide,
  }: {
    appState: State;
    onstate: StateHandler;
    onnavigate: Navigate;
    onguide: (kind: ImportKind) => void;
  } = $props();
  let selectedId = $state('');
  let success = $state('');
  let selected = $derived(
    appState.requests.find((item) => item.request_id === selectedId) ?? appState.requests[0],
  );
</script>

<header class="page-heading">
  <div>
    <div class="eyebrow">Работа с документами</div>
    <h1>Заявки</h1>
    <p>Сохраните список покупателя. Дальше подберём товары и рассчитаем предложение.</p>
  </div>
  <button class="button ghost" onclick={() => onguide('request')}
    ><Icon name="book" size={18} />Как подготовить файл</button
  >
</header>
{#if success}<Notice tone="success" title={success} />{/if}
{#if !appState.requests.length}
  <div class="onboarding-layout">
    <section class="panel first-upload">
      <div class="section-kicker"><span class="step-number">1</span>Заявка покупателя</div>
      <h2>Какие товары нужны?</h2>
      <p class="section-description">
        Загрузите файл с артикулами, названиями и количеством. Если артикула нет, его можно будет
        уточнить при подготовке КП.
      </p>
      <UploadPanel
        kind="request"
        {appState}
        {onstate}
        {onguide}
        oncommitted={(preview) => {
          selectedId = preview.request_id ?? '';
          success = `Заявка ${preview.request_id} сохранена`;
        }}
      />
    </section>
    <aside class="start-aside">
      <div class="mini-document">
        <div class="mini-line long"></div>
        <div class="mini-line"></div>
        <div class="mini-grid">
          <span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
        <div class="mini-stamp"><Icon name="check" size={22} /></div>
      </div>
      <h3>От заявки до готового PDF</h3>
      <ol class="simple-steps">
        <li>
          <span>1</span>
          <div>
            <b>Загрузите заявку</b>
            <p>Что и сколько нужно покупателю</p>
          </div>
        </li>
        <li>
          <span>2</span>
          <div>
            <b>Добавьте прайс</b>
            <p>Товары, упаковки и исходные цены</p>
          </div>
        </li>
        <li>
          <span>3</span>
          <div>
            <b>Подготовьте предложение</b>
            <p>Уточните данные и скачайте КП</p>
          </div>
        </li>
      </ol>
    </aside>
  </div>
{:else}
  <details class="panel import-disclosure">
    <summary
      ><div>
        <Icon name="upload" size={19} /><strong>Загрузить заявку</strong><span
          >Новую или обновлённую</span
        >
      </div>
      <Icon name="chevronDown" size={18} /></summary
    ><UploadPanel
      compact
      kind="request"
      {appState}
      {onstate}
      {onguide}
      oncommitted={(preview) => {
        selectedId = preview.request_id ?? '';
        success = `Заявка ${preview.request_id} сохранена`;
      }}
    />
  </details>
  <div class="request-layout">
    <section class="request-list" aria-label="Сохранённые заявки">
      <div class="list-caption">Сохранённые <span>{appState.requests.length}</span></div>
      {#each appState.requests as item}<button
          class:active={selected?.request_id === item.request_id}
          class="request-card"
          onclick={() => (selectedId = item.request_id)}
          ><span class="request-card-title"
            ><Icon name="file" size={19} /><b>{item.request_id}</b><Icon
              name="chevron"
              size={16}
            /></span
          ><strong>{item.buyer.company_name || 'Покупатель пока не указан'}</strong><span
            >{count(item.rows.length)} · {date(item.uploaded_at)}</span
          ></button
        >{/each}
    </section>
    {#if selected}<section class="panel request-detail">
        <div class="panel-topline">
          <div>
            <div class="eyebrow">Содержимое заявки</div>
            <h2>{selected.request_id}</h2>
            <p>{selected.filename} · загружен {date(selected.uploaded_at, true)}</p>
          </div>
          <button
            class="button primary small"
            onclick={() => onnavigate('quote', selected.request_id)}
            >Подготовить КП<Icon name="arrow" size={17} /></button
          >
        </div>
        <div class="table-scroll">
          <table>
            <thead
              ><tr
                ><th class="row-number">№</th><th>Товар покупателя</th><th>Артикул</th><th
                  class="numeric">Количество</th
                ></tr
              ></thead
            ><tbody
              >{#each selected.rows as row}<tr
                  ><td class="muted">{row.line}</td><td><strong>{row.name}</strong></td><td
                    class="mono">{row.sku || 'Не указан'}</td
                  ><td class="numeric">{row.quantity} шт.</td></tr
                >{/each}</tbody
            >
          </table>
        </div>
        <div class="panel-footer">
          <Icon name="info" size={16} />
          <p>Количество в заявке всегда указано в штуках. Упаковки учтём по прайсу.</p>
        </div>
      </section>{/if}
  </div>
{/if}
<div class="roadmap-note">
  <Icon name="link" size={17} />
  <p>
    Сейчас данные загружаются из файлов. В дальнейшем можно подключить их получение напрямую из
    вашей учётной системы.
  </p>
</div>
