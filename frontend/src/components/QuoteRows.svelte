<script lang="ts">
  import type { Draft, Product, QuoteLine, RequestRecord } from '../lib/types';
  import { decimal, money, statuses } from '../lib/format';
  import Icon from './Icon.svelte';
  let {
    request,
    quote,
    busy,
    onselection,
    onresolve,
    onpriceedit,
  }: {
    request: RequestRecord;
    quote: Draft;
    busy: boolean;
    onselection: (lines: number[]) => void;
    onresolve: (line: QuoteLine) => void;
    onpriceedit: (product: Product) => void;
  } = $props();
  let expanded = $state<number | null>(null);
  let allSelected = $derived(request.selected_lines.length === request.rows.length);
  function lineResult(line: number) {
    return quote.lines.find((item) => item.request.line === line);
  }
  function toggle(line: number) {
    onselection(
      request.selected_lines.includes(line)
        ? request.selected_lines.filter((item) => item !== line)
        : [...request.selected_lines, line].sort((a, b) => a - b),
    );
  }
</script>

<div class="selection-toolbar">
  <label class="checkbox-label"
    ><input
      type="checkbox"
      checked={allSelected}
      indeterminate={!allSelected && request.selected_lines.length > 0}
      disabled={busy}
      onchange={() => onselection(allSelected ? [] : request.rows.map((item) => item.line))}
    /><span>Все строки заявки</span></label
  ><span>В КП: <b>{request.selected_lines.length}</b> из {request.rows.length}</span>
</div>
<div class="table-scroll quote-items">
  <table>
    <thead
      ><tr
        ><th><span class="visually-hidden">Включить</span></th><th>Товар из заявки</th><th
          >Количество</th
        ><th class="numeric">Сумма с НДС, ₽</th><th>Проверка</th></tr
      ></thead
    ><tbody>
      {#each request.rows as row}
        {@const line = lineResult(row.line)}
        {@const included = request.selected_lines.includes(row.line)}
        <tr class:excluded={!included}>
          <td class="check-cell"
            ><input
              type="checkbox"
              checked={included}
              disabled={busy}
              aria-label={`Включить в КП: ${row.name}`}
              onchange={() => toggle(row.line)}
            /></td
          >
          <td class="quote-product"
            ><strong>{row.name}</strong><span class="cell-subtitle mono"
              >{row.sku || 'Без артикула'}</span
            >{#if line?.selected && (line.manually_selected || line.selected.sku !== row.sku)}<span
                class="chosen-product"
                >Выбран: {line.selected.sku}{line.selected.name !== row.name
                  ? ` · ${line.selected.name}`
                  : ''}</span
              >{/if}</td
          >
          <td
            ><strong>{row.quantity} шт.</strong
            >{#if line?.sale_quantity && line.selected?.unit === 'упак'}<span class="cell-subtitle"
                >{line.sale_quantity} упак. × {line.selected.pack_size} шт.</span
              >{/if}</td
          >
          <td class="numeric"
            ><strong>{included ? money(line?.total_with_vat) : '—'}</strong
            >{#if line?.status === 'confirmed'}<button
                class="text-button calculation-link"
                onclick={() => (expanded = expanded === row.line ? null : row.line)}
                aria-expanded={expanded === row.line}
                >Расчёт<Icon name="chevronDown" size={13} /></button
              >{/if}</td
          >
          <td class="quote-action"
            >{#if !included}<span class="tag neutral">Не включено</span>{:else if !line}<span
                class="muted">Пересчитываем…</span
              >{:else if line.status === 'confirmed'}<span class="status-ready"
                ><Icon name="check" size={15} />Рассчитано</span
              >{#if line.manually_selected}<button
                  class="text-button"
                  disabled={busy}
                  onclick={() => onresolve(line)}>Изменить выбор</button
                >{/if}{:else if line.status === 'missing_price' && line.selected}<button
                class="action-pill"
                disabled={busy}
                onclick={() => line.selected && onpriceedit(line.selected)}
                ><Icon name="edit" size={14} />Указать цену</button
              >{:else if line.status === 'quantity_mismatch'}<button
                class="action-pill"
                disabled={busy}
                onclick={() => (expanded = expanded === row.line ? null : row.line)}
                >Проверить количество</button
              >{:else}<button class="action-pill" disabled={busy} onclick={() => onresolve(line)}
                >{line.status === 'not_found' ? 'Нет в прайсе' : 'Выбрать товар'}<Icon
                  name="chevron"
                  size={14}
                /></button
              >{/if}</td
          >
        </tr>
        {#if expanded === row.line && line}
          <tr class="calculation-row"
            ><td colspan="5"
              ><div class="calculation-detail">
                {#if line.status === 'confirmed' && line.selected}<div>
                    <span>Исходная цена</span><b
                      >{money(line.selected.price, true)} / {line.selected.unit}</b
                    ><small>{line.selected.price_basis === 'net' ? 'без НДС' : 'НДС включён'}</small
                    >
                  </div>
                  <span class="calculation-operator">−</span>
                  <div>
                    <span>Скидка</span><b>{decimal(quote.discount_percent)}%</b><small
                      >{money(line.discounted_price, true)} после скидки</small
                    >
                  </div>
                  <span class="calculation-operator">→</span>
                  <div>
                    <span>Цена с НДС</span><b>{money(line.unit_price_with_vat, true)}</b><small
                      >× {line.sale_quantity} {line.selected.unit}</small
                    >
                  </div>
                  <span class="calculation-operator">=</span>
                  <div>
                    <span>Сумма строки</span><b>{money(line.total_with_vat, true)}</b><small
                      >в том числе НДС {money(line.vat_amount, true)}</small
                    >
                  </div>
                  <div class="calculation-source">
                    <span>Источник: {line.selected.source}</span><button
                      type="button"
                      class="text-button"
                      disabled={busy}
                      onclick={() => line.selected && onpriceedit(line.selected)}
                      >Изменить цену в прайсе</button
                    >
                  </div>{:else}<div>
                    <strong>{statuses[line.status]}</strong>
                    <p>{line.note}</p>
                    <p>
                      Согласуйте количество с покупателем и загрузите исправленную заявку с тем же
                      номером. Приложение не округляет его до лишней упаковки.
                    </p>
                  </div>{/if}
              </div></td
            ></tr
          >
        {/if}
      {/each}
    </tbody>
  </table>
</div>
