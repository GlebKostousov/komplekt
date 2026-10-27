import type { Buyer, LineStatus } from './types';

/** Форматирование десятичной строки без пересчёта денег в браузере. */
export function money(value: string | null | undefined, currency = false): string {
  if (value === null || value === undefined) return '—';
  const [whole, fraction = ''] = value.split('.');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0');
  return `${grouped},${fraction.padEnd(2, '0').slice(0, 2)}${currency ? '\u00a0₽' : ''}`;
}
export function decimal(value: string): string {
  return value.replace(/\.0+$/, '').replace('.', ',');
}
export function date(value: string, time = false): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    ...(time ? { hour: '2-digit', minute: '2-digit' } : {}),
    timeZone: 'Europe/Moscow',
  }).format(new Date(value));
}
export function count(
  value: number,
  forms: [string, string, string] = ['позиция', 'позиции', 'позиций'],
): string {
  const tail = value % 100;
  const index =
    tail >= 11 && tail <= 14
      ? 2
      : value % 10 === 1
        ? 0
        : value % 10 >= 2 && value % 10 <= 4
          ? 1
          : 2;
  return `${value} ${forms[index]}`;
}
export const statuses: Record<LineStatus, string> = {
  confirmed: 'Рассчитано',
  needs_clarification: 'Выберите товар',
  missing_price: 'Нужна цена',
  not_found: 'Нет в прайсе',
  quantity_mismatch: 'Проверьте количество',
};
export const buyerLabels: Record<keyof Buyer, string> = {
  company_name: 'Название организации',
  inn: 'ИНН',
  kpp: 'КПП',
  ogrn: 'ОГРН / ОГРНИП',
  address: 'Адрес',
  contact_name: 'Контактное лицо',
  email: 'Электронная почта',
  phone: 'Телефон',
  bank_name: 'Название банка',
  bik: 'БИК',
  account: 'Расчётный счёт',
  correspondent_account: 'Корреспондентский счёт',
};
export function buyerFieldLabel(key: string): string {
  return buyerLabels[key as keyof Buyer] ?? key;
}
