# LT-54873 — прогресс реализации

## 02.11.2026

Ветка `feature/LT-54873-order-supplier-resolver` пересоздана от `develop` (`2758e0d28`).

### Сделано

- **Миграция** `20261102074626_create_order_supplier_snapshots`: таблица `order_supplier_snapshots` (решение, `rule`, `trace`, `version`, `current`, `reason`, `created_by_id`), уникальность `(order_id, version)`, индекс `(order_id, current)`. `db/schema.rb` правлен вручную в старом формате.
- **`OrderSuppliers::Resolver`** — правила LT-55181 перенесены из `ForPackageQuery`, `Package` и `OrderDecorator`:
  - `#operator_organization` — юр лицо пакета (сертификат, 113, отель Динамики: юр лицо оплаты → юр лицо оператора поставщика по гео → Alfi S → «Внешний поставщик» → фолбэк; остальные — `ForPackageQuery`);
  - `#decide(organization)` — решение от заданного юр лица пакета;
  - `#call(traced:)` — полный расчёт.
  Константы `DYNAMIC_SUPPLIER_RULES_SINCE`, `HOTEL_OWNER_DETAILS_SINCE`, `SUPPLIER_DIRECT_PAYMENT_COUNTRY_IDS`, `RUBLE_HOTEL_COUNTRY_IDS` теперь в резолвере.
- **`OrderSuppliers::Decision`** — пять полей решения, `rule`, `trace`; `principal`, `principal_details`, `same_as?`, `summary` для лога.
- **`OrderSupplierSnapshot`**, **`OrderSuppliers.current`** (снимок, иначе на лету от сохранённого юр лица пакета), **`OrderSuppliers.record!`** (новая версия под блокировкой строки заказа, юр лицо пакета и версия договора приводятся к решению), **`OrderSuppliers.record_initial!`** (v1 при создании заказа; ручной пакет 78 выбирает юр лицо заново).
- **`Order#supplier_decision`** — точка чтения с кешем на экземпляре, сбрасывается в `record!` и `reload`.
- **`OrderSuppliers::Recalculation`** — пересчёт с причиной; совпало — `:unchanged`; детализирован и без `force` — `:skipped`, лог, колонка пакета остаётся на юр лице снимка.
- **Триггеры:**
  - `Order after_create :record_supplier_snapshot` (вместо `set_operator_organization`);
  - `Order after_update :recalculate_supplier` при смене `search_type` или `package_id` (вместо `refresh_manual_operator_organization`);
  - `Package after_save :recalculate_order_supplier` при смене `operator_id`/`departure_id` у пакета с заказом; `before_save :update_operator_organization` остался только для пакетов без заказа.
- **Удалено:** `Package#refresh_manual_operator_organization`, `#refresh_operator_organization`, `#external_dynamic_operator_id`, `#dynamic_supplier_rules?`, `#external_dynamic_agreement?`, `#paid_through_payment_organization?`, `#detected_operator`, `#dynamic_rules_organization?`, `#external_supplier_organization?`, `#supplier_operator_organization?`, `#detected_operator_organization`; ветки Динамики из `ForPackageQuery#call`; rake `external_dynamic_matchings:recalculate_organizations`.
- **Потребители:**
  - договор (`OrderDecorator#operator_info`, `#operator_info_markdown`, `#operator_agreement_manager`, `#operator_info_version`, `#detected_operator`) читает решение;
  - `hotel_owner_details?`/`hotel_owner_organization` — делегаты решения (их читает `FiscalProcessor::AgentSupplier`);
  - агент тура в чеке — `LineItemsV2::Advanced::Creator.tour_supplier_id` = юр лицо поставщика из решения;
  - справка о стоимости, `Order#price_info`, Альфа-Мили — принципал;
  - PAPI v3 `operator_organization` (orders, clients, package_common) — `OrderDecorator#supplier_details`: реквизиты принципала и `operator_info` тем же текстом, что в договоре;
  - `admin/agreement_debug` — поля решения.
- **Админка заказа:** панель «Поставщик» (решение, история версий) и `member_action :recalculate_supplier` (`force: true`, подтверждение у детализированного заказа). Доступ — правило роли `admin_orders` → `recalculate_supplier`.
- **Rake:** `order_suppliers:backfill` (v1 `backfill` заказам с 12.10 без снимка, решение от сохранённого юр лица) и `order_suppliers:recalculate` (`rules_changed`; `ORDER_IDS` или `SINCE`).
- **Документация PAPI v3:** `operator_organization` описан в `orders` show/create (3.0, 3.12, 3.16) и `clients` orders/order (3.0, 3.12, 3.16). `validate-sequential` падает на `departure_pages/3.0.yml` так же, как на `develop`.
- **Переводы** `ru.yml`: модель и атрибуты снимка, `order_suppliers.*` (причины, правила, лог), `admin.order_suppliers.*`.

### Тесты

- Новые: `spec/services/order_suppliers/resolver_spec.rb` (табличный, 51 пример: сюда перенесены примеры Динамики из `for_package_query_spec`, `#external_dynamic_operator_id` и `#supplier_operator_organization?` из `package_spec`, условия владельца из `order_decorator_spec`), `recalculation_spec.rb`, `spec/services/order_suppliers_spec.rb`, `spec/lib/tasks/order_suppliers_spec.rb`.
- Обновлены: `order_decorator_spec` (рендер из решения, `#supplier_details`), `order_spec` (снимок при создании и смене типа поиска), `package_spec` (смена вылета у пакета заказа), `order_price_content_renderer_spec` (принципал), спеки чеков (`assign_order_supplier` из `spec/support/order_supplier_helper.rb` вместо `update_columns` юр лица пакета), `packages_controller_spec` (заглушка колбэка).
- Проверено мутацией: поломка правила Абхазии ловится двумя примерами резолвера.
- Регрессия (`spec/models/{order,package,payment}_spec.rb`, `spec/models/order`, `spec/services/{accounting,receipts,partner_bonuses,statement_templates,line_items_v2,order,order_suppliers}`, `spec/apis/fiscal_processor`, `spec/controllers/papi/v3`, `spec/requests/papi/v3`, `spec/lib/tasks`, `spec/queries`, `spec/decorators`, `spec/workers/receipt_fiscalizer_spec.rb`, `spec/admin/receipt_tools_spec.rb`): 2360 примеров, 8 падений — те же 8, что на чистом `develop` (2339 примеров): нет таблицы `old_packages_2` в локальной базе, роли в `agency_order_flow`, `checkout_flow`, `hooks_controller`, `new_telephony`, `page_information`.
- Первый прогон регрессии дал 218 падений из-за параллельного запуска второго rspec на той же тестовой базе; не повторять.
- Добавлен пример: решение для ещё не сохранённого заказа (prebuild) берёт владельца на текущую дату, а не падает на `created_at = nil`.

### Rejected / changed

- **Тип поиска для владельца.** Спека: все правила читают `organization_search_type`. Сделано: единый тип (`organization_search_type`) у выбора юр лица и признака договора поставщика; правило владельца по-прежнему читает `Order#hotel?` (`orders.search_type`). У ручного пакета они совпадают, а у обычного пакета без `pb_tour` смена правила владельца изменила бы поведение.
- **PAPI v2 `reports/order_for_templates`** не трогали: шаблон ссылается на неопределённую локальную `order` и на метод с опечаткой `operator_agreeement_version`, то есть не работает и до задачи.
- **`Package#dynamic_hotel_without_supplier?`** остался в `Package`: это классификация сохранённого юр лица для лога «Не найден поставщик для пакета», а не правило выбора.
- **`ForPackageQuery#fallback_call`** — новый публичный вход: резолверу нужен фолбэк без гео для отеля Динамики, как было в `dynamic_hotel_organization`.
- **Ошибки записи снимка** в колбэках заказа и пакета перехватываются и уходят в Sentry: заказ создаётся, решение считается на лету.
- **Пересчёт без изменений** у заказа без снимка снимок не создаёт: решение на лету и так совпадает.
- **`price_info[].organization`** в документации PAPI v3 не описан ни до, ни после; форма поля не изменилась, описывать его отдельно не стали.
- **Спеки админки** не пишем (решение пользователя 02.11).

### Выкатка

1. Миграция.
2. В админке ролей добавить правило `admin_orders` → `recalculate_supplier` нужным ролям.
3. `rake order_suppliers:backfill`.
