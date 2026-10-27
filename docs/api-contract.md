# Внутренний контракт приложения

Приложение «Комплект». Python 3.13 / FastAPI / SQLite, Svelte 5 / TypeScript / Vite. Пользователь запускает готовую сборку интерфейса вместе с Python одним скриптом; Node нужен только разработчику. Нет аутентификации и прав: локальная учебная версия, общий набор данных. Не публиковать сейчас.

## Общее

Все API по `/api`. Деньги и проценты в JSON — десятичные **строки**, не float. Все изменения принимают целочисленное поле `revision` из последнего State. Если данные уже изменились, HTTP 409 с понятной ошибкой и предложение обновить страницу. Файл максимум 1 МиБ; прайс максимум 2000 строк, заявка максимум 200 строк. Одна заявка в одном CSV. Все записи сохраняются в SQLite между перезапусками.

Ошибка: `{code: string, message: string, issues: [{row: number|null, field: string|null, value: string|null, message: string}]}`. Коды прикладных ошибок — `INVALID_INPUT`, `INVALID_CSV`, `CONFLICT`, `NOT_FOUND`, `STORAGE_ERROR`, `OUTPUT_ERROR`, `INTERNAL_ERROR`. Статус HTTP задан у самой ошибки. В ответе нет traceback. Непойманный сбой — HTTP 500 и `INTERNAL_ERROR`.

## State

`GET /api/state` и результат всех обычных изменений:

```
{
 revision: number,
 catalog: {generation: string, filename: string, uploaded_at: string, sha256: string, products: Product[]} | null,
 requests: RequestRecord[],
 quotes: QuoteSummary[],
 seller: Seller,
 assumptions: string[]
}
```

`Product`: `{id, sku, name, unit: "шт"|"упак", pack_size: number, price: string|null, price_basis: "net"|"gross", vat_rate: "20", source, updated_at}`.

`RequestRow`: `{request_id, line: number, sku, name, quantity: number, unit: "шт"}`.

`Buyer` — все поля строковые, пустая строка допустима при сохранении черновика: `company_name, inn, kpp, ogrn, address, contact_name, email, phone, bank_name, bik, account, correspondent_account`. Для готового КП нужны company_name, inn, address. Непустые значения строго проверяются, ИНН / ОГРН — контрольные цифры, связь ИП/КПП, банковские реквизиты.

`RequestRecord`: `{request_id, filename, sha256, uploaded_at, rows: RequestRow[], buyer: Buyer, buyer_draft: Buyer, selected_lines: number[], choices: Record<string,string>, discount_percent: string, discount_draft: string}`. `buyer` и `discount_percent` — уже проверенные значения. `buyer_draft` и `discount_draft` — то, что человек ещё набирает. choices связывает номер строки заявки с Product.id. По умолчанию выбраны все строки, скидка 10%.

`Seller`: `{company_name, inn, kpp, ogrn, address, phone, email, website, bank_name, bik, account, correspondent_account, manager, manager_title}`. Фиксированная вымышленная компания «ООО Ладога Комплект Демо». Раздела «Компания» нет.

## Загрузка CSV

`POST /api/imports/{price|request}/preview`: multipart поле `file`. Проверяет файл целиком, НЕ меняет текущие товары / заявки. Результат:

```
{token, revision, kind, filename, row_count, request_id: string|null,
 rows: Record<string,string|number|null>[],
 warnings: Issue[],
 changes: {added: number, changed: number, removed: number, replaces_request: boolean},
 expires_at: string}
```

`POST /api/imports/commit`: `{token, revision}` -> State. Превью действительно 30 минут. Перед применением показать число добавленных, изменённых и удалённых товаров и предупреждение, что ручные цены и выбор соответствий сбросятся. Новый прайс **полностью удаляет старые сущности и создаёт новые**, сбрасывает choices всех заявок. Старые выпущенные КП остаются неизменными. Повторная заявка с тем же request_id обновляет одну существующую; при изменённом содержимом сбрасывает подбор/выбор строк, сохраняет покупателя. Повтор точно того же файла не сбрасывает правки.

`GET /api/examples/{request|price}.csv` -> исходные образцы. UTF-8 с BOM для Excel, разделитель `;`. Исходные приложенные CSV также принимаются без изменений.

## Изменения

`PATCH /api/products/{product_id}`: `{revision, price: string|null, source: string}` -> State. Меняет текущую сущность во всём приложении. Пустое поле цены -> null, не 0. Источник обязателен, UI предлагает «Уточнено вручную» и позволяет уточнить. Вводить число без ₽, до 2 знаков, точка или запятая.

`PATCH /api/requests/{request_id}/buyer`: `{revision, buyer: Buyer}` -> State. Успешное сохранение копирует реквизиты и в черновик.

`PATCH /api/requests/{request_id}/draft`: `{revision, buyer_draft: Buyer, discount_draft: string}` -> State. Черновик не проверяет контрольные цифры. `discount_draft` — не длиннее 16 знаков. Проверенные реквизиты и скидка при этом не меняются.

`PUT /api/requests/{request_id}/selection`: `{revision, lines: number[]}` -> State. Только строки этой заявки, можно временно снять все, но нельзя выпустить пустое КП.

`PUT /api/requests/{request_id}/choices/{line}`: `{revision, product_id: string|null}` -> State. Выбор из текущего прайса, null сбрасывает явный выбор. Для неоднозначного имени показывает кандидатов; для отсутствующего SKU можно явно выбрать замену из прайса, предупреждая пользователя. Исходная строка сохраняется.

`PATCH /api/requests/{request_id}/discount`: `{revision, discount_percent: string}` -> State. 0–100%, до 2 десятичных знаков.

## Расчёт и PDF

`GET /api/requests/{request_id}/calculation` -> `{revision, quote: Draft}`.

`Draft`: `{request_id, lines: QuoteLine[], discount_percent, vat_rate: "20", currency: "RUB", confirmed_count, unresolved_count, selected_count, excluded_count, calculation_complete: boolean, is_complete: boolean, missing_buyer_fields: string[], subtotal_with_vat, vat_amount, buyer: Buyer, request_source: {name,sha256}, price_source: {name,sha256}|null}`.

`QuoteLine`: `{request: RequestRow, status: "confirmed"|"needs_clarification"|"missing_price"|"not_found"|"quantity_mismatch", selected: Product|null, sale_quantity: number|null, discounted_price: string|null, unit_price_with_vat: string|null, total_with_vat: string|null, vat_amount: string|null, candidates: Product[], note: string, manually_selected: boolean}`. В lines только выбранные пользователем строки заявки, исключённые отражены счётчиком и отдельно видны в UI. Неполный расчёт показывает подытог, не итог заказа.

`POST /api/quotes`: заголовок `Idempotency-Key` из 32 шестнадцатеричных знаков и тело `{revision, request_id, allow_incomplete: boolean}` -> `{state: State, quote_id: string}`. Без ключа — HTTP 422. Повтор с тем же ключом возвращает первый документ и не создаёт второй. При неполных данных без подтверждения HTTP 422. Сохраняет снимок расчёта, покупателя, продавца, источников и сам PDF. `QuoteSummary`: `{id, number, created_at, request_id, buyer_name, subtotal_with_vat, vat_amount, is_complete, selected_count, unresolved_count, filename}`.

`GET /api/quotes/{id}` -> сохранённый документ `{id, number, created_at, seller, quote: Draft}`.

`GET /api/quotes/{id}/pdf` -> скачивание PDF. `?inline=true` для просмотра. Скачивается именно сохранённый PDF, без пересчёта.

## UI

Навигация: «Заявки», «Прайс», «Подготовка КП», «История КП». Основные действия настоящие, все данные через API. Пустое состояние с образцами; без случайно заселённых данных. Общая плашка: «Учебная версия. Без входа и разграничения доступа. Используйте вымышленные данные.» Кнопка/раскрытие «О тестовом задании» содержит все допущения.

Загрузка в два этапа: проверить, затем применить. После успешного прайса предложить заполнить недостающие цены, можно отложить. Подбор в КП: галочки у строк из заявки; для неоднозначной строки выпадающий список кандидатов из прайса. Боковая сводка и хороший читаемый предпросмотр документа. Покупатель — форма в подготовке КП, дополнительные реквизиты раскрываются. Предмет предложения и условия фиксированные, не редактируются. PDF с неполными строками выгружается только после явного предупреждения и с пометкой «Черновик. Не все позиции рассчитаны» в самом файле.

README описывает локальный запуск, проверку на учебных файлах, суммы 3060 / 510 и 3276 / 546, повтор заявки и границы задания. Публичного адреса нет.
