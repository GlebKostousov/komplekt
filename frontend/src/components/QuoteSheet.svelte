<script lang="ts">
  import type { Draft, Seller } from '../lib/types';
  import { money, decimal, statuses } from '../lib/format';
  let {
    quote,
    seller,
    number = 'Предпросмотр',
    createdAt = '',
  }: { quote: Draft; seller: Seller; number?: string; createdAt?: string } = $props();
</script>

<article class="document-sheet" aria-label="Предпросмотр коммерческого предложения">
  <header class="document-header">
    <div class="document-brand">
      <div class="ladoga-mark"><span></span><span></span><span></span></div>
      <div><strong>ЛАДОГА<br />КОМПЛЕКТ</strong><span>Поставка промышленных компонентов</span></div>
    </div>
    <div class="document-contacts">
      <b>{seller.phone}</b><span>{seller.email}</span><span>{seller.website}</span>
    </div>
  </header>
  <div class="document-rule"></div>
  <div class="document-meta">
    <span
      >{number}{createdAt
        ? ` · ${new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow' }).format(new Date(createdAt))}`
        : ''}</span
    ><span>По заявке {quote.request_id}</span>
  </div>
  <h2>Коммерческое предложение</h2>
  <div class="document-recipient">
    <span>Покупатель</span><strong>{quote.buyer.company_name || 'Не указан'}</strong
    >{#if quote.buyer.inn}<p>
        ИНН {quote.buyer.inn}{quote.buyer.kpp ? ` · КПП ${quote.buyer.kpp}` : ''}
      </p>{/if}{#if quote.buyer.ogrn}<p>
        ОГРН / ОГРНИП {quote.buyer.ogrn}
      </p>{/if}{#if quote.buyer.address}<p>
        {quote.buyer.address}
      </p>{/if}{#if quote.buyer.contact_name || quote.buyer.phone || quote.buyer.email}<p>
        {[quote.buyer.contact_name, quote.buyer.phone, quote.buyer.email]
          .filter(Boolean)
          .join(' · ')}
      </p>{/if}{#if quote.buyer.bank_name || quote.buyer.bik}<p>
        {[quote.buyer.bank_name, quote.buyer.bik ? `БИК ${quote.buyer.bik}` : '']
          .filter(Boolean)
          .join(' · ')}
      </p>{/if}{#if quote.buyer.account || quote.buyer.correspondent_account}<p>
        {[
          quote.buyer.account ? `р/с ${quote.buyer.account}` : '',
          quote.buyer.correspondent_account ? `к/с ${quote.buyer.correspondent_account}` : '',
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>{/if}
  </div>
  {#if !quote.is_complete}<div class="document-warning">
      <strong>Черновик</strong><span
        >{!quote.calculation_complete
          ? 'Не все позиции рассчитаны. Подытог не отражает стоимость всей заявки.'
          : 'Реквизиты покупателя заполнены не полностью.'}</span
      >
    </div>{/if}
  <h3>Предмет предложения</h3>
  <p>
    Предлагаем поставку промышленных компонентов по вашей заявке. Состав и стоимость указаны ниже.
  </p>
  <table class="document-table">
    <thead
      ><tr
        ><th>№</th><th>Наименование / артикул</th><th>Кол-во</th><th>Цена с НДС, ₽</th><th
          >Сумма, ₽</th
        ></tr
      ></thead
    ><tbody
      >{#each quote.lines as line}<tr
          ><td>{line.request.line}</td><td
            ><strong>{line.selected?.name ?? line.request.name}</strong><small
              >{line.selected?.sku || line.request.sku || 'Артикул не указан'}</small
            >{#if line.status !== 'confirmed'}<span class="document-line-note"
                >{statuses[line.status]}</span
              >{/if}</td
          ><td
            >{line.sale_quantity ?? line.request.quantity}
            {line.sale_quantity !== null ? (line.selected?.unit ?? 'шт') : 'шт'}</td
          ><td>{money(line.unit_price_with_vat)}</td><td>{money(line.total_with_vat)}</td></tr
        >{/each}</tbody
    >
  </table>
  <div class="document-totals">
    <span>Скидка {decimal(quote.discount_percent)}% учтена в цене</span>
    <div>
      <p>
        <span>{quote.calculation_complete ? 'Итого с НДС' : 'Подытог рассчитанных позиций'}</span
        ><strong
          >{quote.confirmed_count ? money(quote.subtotal_with_vat, true) : 'Не рассчитан'}</strong
        >
      </p>
      <p class="vat">
        <span>В том числе НДС 20%</span><span
          >{quote.confirmed_count ? money(quote.vat_amount, true) : '—'}</span
        >
      </p>
    </div>
  </div>
  <h3>Условия поставки</h3>
  <p>
    Цены указаны в рублях. Оплата — 100% предоплата после согласования заказа. Срок и способ
    доставки согласуются отдельно. Предложение действительно в течение 10 календарных дней.
  </p>
  <div class="document-next">
    <strong>Для согласования заказа свяжитесь с менеджером.</strong>
    <p>{seller.manager} · {seller.manager_title}<br />{seller.phone} · {seller.email}</p>
  </div>
  <footer class="document-footer">
    <strong>{seller.company_name}</strong>
    <p>
      ИНН {seller.inn} · КПП {seller.kpp} · ОГРН {seller.ogrn}<br />{seller.address}<br
      />{seller.bank_name} · БИК {seller.bik}<br />р/с {seller.account} · к/с {seller.correspondent_account}
    </p>
    <span>Учебный образец. Компания и реквизиты вымышлены.</span>
  </footer>
</article>
