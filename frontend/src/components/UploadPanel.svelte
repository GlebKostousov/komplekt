<script lang="ts">
  import { api, problemFrom } from '../lib/api';
  import { count, money } from '../lib/format';
  import type { ApiProblem, ImportKind, ImportPreview, State, StateHandler } from '../lib/types';
  import Icon from './Icon.svelte';
  import Modal from './Modal.svelte';
  import Notice from './Notice.svelte';
  import Problem from './Problem.svelte';
  let {
    kind,
    appState,
    onstate,
    onguide,
    oncommitted,
    compact = false,
  }: {
    kind: ImportKind;
    appState: State;
    onstate: StateHandler;
    onguide: (kind: ImportKind) => void;
    oncommitted?: (preview: ImportPreview, appState: State) => void;
    compact?: boolean;
  } = $props();
  let busy = $state(false);
  let dragging = $state(false);
  let problem = $state<ApiProblem | null>(null);
  let preview = $state<ImportPreview | null>(null);
  let fileInput: HTMLInputElement;

  async function checkFile(file: File | undefined) {
    if (!file || busy) return;
    problem = null;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      problem = {
        code: 'file_type',
        message: 'Нужен файл CSV. Сохраните таблицу в формате CSV UTF-8 и загрузите её снова.',
        issues: [],
      };
      fileInput.value = '';
      return;
    }
    if (file.size > 1048576) {
      problem = {
        code: 'file_size',
        message: 'Файл больше 1 МБ. Уберите лишние строки и сохраните его ещё раз.',
        issues: [],
      };
      fileInput.value = '';
      return;
    }
    busy = true;
    const body = new FormData();
    body.append('file', file);
    try {
      preview = await api<ImportPreview>(`/imports/${kind}/preview`, { method: 'POST', body });
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
      fileInput.value = '';
    }
  }
  async function commit() {
    if (!preview) return;
    busy = true;
    problem = null;
    try {
      const next = await api<State>('/imports/commit', {
        method: 'POST',
        body: JSON.stringify({ token: preview.token, revision: preview.revision }),
      });
      const applied = preview;
      preview = null;
      onstate(next);
      oncommitted?.(applied, next);
    } catch (error) {
      problem = problemFrom(error);
    } finally {
      busy = false;
    }
  }
  function dropped(event: DragEvent) {
    event.preventDefault();
    dragging = false;
    if (event.dataTransfer?.files.length !== 1) {
      problem = { code: 'file_count', message: 'Загрузите один файл за раз.', issues: [] };
      return;
    }
    void checkFile(event.dataTransfer.files[0]);
  }
</script>

<div class:compact class="upload-wrap">
  <div
    class:dragging
    class:busy
    class="upload-drop"
    role="group"
    aria-label={kind === 'request' ? 'Загрузка заявки' : 'Загрузка прайса'}
    ondragover={(event) => {
      event.preventDefault();
      dragging = true;
    }}
    ondragleave={() => (dragging = false)}
    ondrop={dropped}
  >
    <span class="upload-symbol"><Icon name="upload" size={25} /></span>
    <div class="upload-copy">
      <strong
        >{busy
          ? 'Проверяем файл…'
          : kind === 'request'
            ? 'Загрузите заявку покупателя'
            : 'Загрузите прайс поставщика'}</strong
      >
      <p>{busy ? 'Текущие данные пока не меняются.' : 'Перетащите CSV сюда или выберите файл'}</p>
      <span class="file-requirements">CSV · до 1 МБ · UTF-8 · разделитель «;»</span>
    </div>
    <input
      bind:this={fileInput}
      id={`file-${kind}`}
      type="file"
      accept=".csv,text/csv"
      class="visually-hidden"
      disabled={busy}
      onchange={() => checkFile(fileInput.files?.[0])}
    />
    <label for={`file-${kind}`} class="button secondary" class:disabled={busy}
      ><Icon name="plus" size={17} />Выбрать файл</label
    >
  </div>
  <div class="upload-links">
    <button class="text-button" type="button" onclick={() => onguide(kind)}
      ><Icon name="book" size={16} />Как заполнить файл</button
    >
    <a href={`/api/examples/${kind}.csv`} download class="text-button"
      ><Icon name="download" size={16} />Скачать образец</a
    >
  </div>
  {#if !preview}<Problem {problem} />{/if}
</div>
{#if preview}
  <Modal
    title="Файл проверен"
    subtitle={preview.filename}
    wide
    onclose={() => {
      if (!busy) {
        preview = null;
        problem = null;
      }
    }}
  >
    <div class="import-result">
      <span class="result-check"><Icon name="check" size={24} /></span>
      <div>
        <h3>{count(preview.row_count)} {kind === 'price' ? 'в прайсе' : 'в заявке'}</h3>
        <p>
          {kind === 'request'
            ? `Заявка ${preview.request_id}. Можно сохранить данные.`
            : 'Структура и значения проверены. Можно сохранить товары.'}
        </p>
      </div>
    </div>
    {#if kind === 'price' && appState.catalog}
      <Notice tone="warning" title="Этот прайс полностью заменит текущий">
        <p>
          Старые товары и внесённые вручную цены будут удалены. Выбор товаров в заявках понадобится
          проверить заново. Уже сохранённые КП останутся прежними.
        </p>
      </Notice>
      <div class="change-strip">
        <span><b>{preview.changes.added}</b> новых</span><span
          ><b>{preview.changes.changed}</b> изменённых</span
        ><span><b>{preview.changes.removed}</b> отсутствуют в новом файле</span>
      </div>
    {:else if preview.changes.replaces_request}
      <Notice title="Заявка с таким номером уже есть">
        <p>
          Её строки будут обновлены. Второй заявки не появится, реквизиты покупателя сохранятся.
          Если содержимое изменилось, выбор строк и товаров понадобится проверить заново.
        </p>
      </Notice>
    {/if}
    {#if preview.warnings.length}
      <Notice tone="warning" title="Некоторые данные нужно уточнить">
        <ul class="issue-list">
          {#each preview.warnings as issue}<li>
              {#if issue.row}Строка {issue.row}.
              {/if}{' '}{issue.message}
            </li>{/each}
        </ul>
        <p>Это не мешает загрузке. Недостающие цены можно внести после неё или заполнить позже.</p>
      </Notice>
    {/if}
    <div class="table-scroll preview-table">
      <table>
        <thead
          ><tr
            ><th>Артикул</th><th>Название</th><th class="numeric"
              >{kind === 'request' ? 'Количество' : 'Цена, ₽'}</th
            ><th>Единица</th></tr
          ></thead
        ><tbody>
          {#each preview.rows.slice(0, 6) as row}<tr
              ><td class="mono">{row.sku || '—'}</td><td>{row.name}</td><td class="numeric"
                >{kind === 'request'
                  ? row.quantity
                  : row.price === null || row.price === ''
                    ? 'Нет цены'
                    : money(String(row.price))}</td
              ><td>{row.unit}</td></tr
            >{/each}
        </tbody>
      </table>
    </div>
    {#if preview.row_count > 6}<p class="footnote">
        Показаны первые 6 строк. Проверен весь файл.
      </p>{/if}
    <Problem {problem} />
    {#snippet footer()}
      <button
        class="button secondary"
        disabled={busy}
        onclick={() => {
          preview = null;
          problem = null;
        }}>Отмена</button
      >
      <button class="button primary" disabled={busy} onclick={commit}
        ><Icon name="check" size={18} />{busy
          ? 'Сохраняем…'
          : kind === 'request'
            ? 'Сохранить заявку'
            : appState.catalog
              ? 'Заменить прайс'
              : 'Сохранить прайс'}</button
      >
    {/snippet}
  </Modal>
{/if}
