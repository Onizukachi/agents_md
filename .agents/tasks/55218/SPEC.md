# LT-55218 API для работы с милями TravelSolutions

## Summary

TravelSolutions (партнёр 1340, субагент с депозитом) хочет оплачивать часть своих заказов альфа-милями клиента. Мили списывает у себя, нам передаёт только сумму, а позже возмещает её деньгами по реестру. Первый этап: учёт миль в заказе, изменение суммы в обе стороны и история операций. Реестры, флаги `verified`/`cleared`, поступление денег и 1С — второй этап.

Ключевые решения:

- Мили — это **скидка** через существующий `PartnerBonus` с новым `kind` `partner_alfa_miles`. Комиссия партнёра считается от цены за вычетом миль (согласовано с бизнесом).
- Программа бонусов партнёра — **один селектор `partners.partner_bonus_kind`** (один `kind` или ничего) вместо булевых флагов на каждую программу. Он заменяет `alfa_miles_enabled`, поле `alfa_miles_enabled` в API настроек партнёра остаётся и вычисляется из селектора. В запросе ручки `kind` не передаётся, он берётся из селектора.
- Мили приходят **отдельной ручкой `POST /papi/v3/orders/:id/partner_bonus` после создания заказа**. Порядок вызовов: `create` → ручка миль → `/payments` на остаток. В `orders#create` новый `kind` не принимается.
- `PartnerBonus.amount` — текущий остаток миль, он же долг партнёра. Каждая операция (`debit`/`refund`) пишется в новый журнал `partner_bonus_operations` с ID операции партнёра: это идемпотентность сейчас и сверка потом.
- Суммы — целые рубли. Деньгами всегда остаётся ≥1 ₽. `debit` не больше долга и запрещён в `canceled`/`annulled`. `refund` не больше остатка и разрешён в любом статусе.
- Деньги по-прежнему возвращает менеджер. Мили при отмене партнёр возвращает только после нашего полного возврата денег. Если мили вернули на отменённом заказе без возврата денег, пишем в лог и Sentry, но не блокируем.

## Problem

TravelSolutions продаёт наши туры как субагент: создаёт заказ через PAPI и платит полную цену с депозита через `POST /orders/:id/payments`. Теперь их клиенты хотят частично платить альфа-милями. Мили списывает TravelSolutions на своей стороне, а эту часть стоимости возмещает нам деньгами позже.

Сейчас:

- Передать нам сумму миль нельзя. Существующий механизм B2C-миль (`alfa_miles`) сам ходит в API Альфы от имени клиента, и субагенту не подходит.
- Нельзя изменить сумму миль после создания заказа. Это нужно, например, при покупке трансфера, изменении цены или отмене.
- Нет истории операций с милями. Нельзя восстановить, когда и на сколько менялась сумма, и потом сверить её с партнёром.

## Solution

Для партнёра:

1. Создаёт заказ как обычно (`POST /papi/v3/orders/create`).
2. Списывает мили у клиента на своей стороне и сообщает нам сумму: `POST /papi/v3/orders/:id/partner_bonus`, `operation=debit`, `amount`, `operation_id`. В ответ получает остаток миль, новую цену заказа и долг.
3. Платит долг деньгами через `POST /orders/:id/payments`. Мили плюс деньги равны стоимости заказа.
4. Если стоимость выросла (допуслуга), снова закрывает долг милями (`debit`) и/или деньгами (`/payments`).
5. Если хочет вернуть клиенту часть миль на активном заказе, шлёт `refund` и доплачивает появившийся долг деньгами.
6. При отмене ждёт нашего возврата денег. Получил вебхук `refund` на всю оплаченную деньгами сумму — возвращает все мили (`refund` на весь остаток). Денег не вернули (штраф 100%) — мили не трогает, остаток остаётся его долгом.

Для нас:

- Мили в заказе работают как скидка партнёрского бонуса: цена, `stat_price` и комиссия партнёра пересчитываются после каждой операции.
- Остаток миль на заказе — сумма, которую партнёр нам должен.
- Журнал операций — основа будущего реестра сверки.
- Деньги по субагентским заказам менеджер возвращает как сейчас: через менеджерку, на депозит, с вебхуком партнёру.

## Current system state

### TravelSolutions (данные Replica на 26–27.10.2026)

- Партнёр 1340 `travel_solutions`: `is_outer_first_line=1`, `deposit_allowed=1`, `is_subagent_hybrid=0`, `skip_fiscalization=1` (чеки пробивает сам партнёр), организация АК (7), комиссия 6% (по некоторым операторам 8% через `operator_commissions`). Настроены `notify_webhook_url` и `refund_webhook_url`.
- Заказы создаются через PAPI (`source=papi`): в октябре 572 заказа на 458 разных клиентов. Платят в среднем через 5 минут после создания, максимум через 2 часа. С сентября 391 заказ отменён без оплаты.
- Оплата идёт только через `POST /orders/:id/payments` со `status=paid`: 677 запросов с августа, `refund` через эту ручку не присылали ни разу. На заказ один платёж `ExternalProcessor`. У 37 платежей несколько списаний (доплаты).
- Все возвраты делает LT: 87 вебхуков `refund`, 175 `cancelation`. 70 отмен с оплатой — полный возврат одной операцией, частичных при отмене не было. 12 частичных возвратов на активных заказах, в среднем около 7 500 ₽.
- Сейчас `partner_bonuses` использует только B2C-партнёр 1220 (`alfa_miles`), `partner_certificates` — только партнёр 1297.

### Субагентские ручки и платежи

- Маршруты: `config/routes/api.rb:203-213`, в том числе `post '/:id/payments'`, `post '/:id/certificate'`.
- `Papi::V3::OrderSubagentMethods` (`app/controllers/concerns/papi/v3/order_subagent_methods.rb`):
  - `before_action :set_token`, `:set_notifiable_order` (стр. 7–8): заказ ищется по `id` и `partner_id`, чужой заказ даёт 404 `order not_found`;
  - `dry_validate` (стр. 10) берёт валидатор `Papi::V3::OrdersController::<Action>ParamsValidator` (`app/validators/papi/v3/orders_controller/`). Подпись — `sha256_chain_signature`, например `CertificateParamsValidator`;
  - `#certificate` (стр. 46) — образец ручки с `Order.lock` и `log_request` (стр. 197, `ExternalRequestLog`, `resource: incoming_partner_hooks`). Перезаписывает абсолютную сумму без истории;
  - `#payments` (стр. 34) → `Subagent::ExternalPaymentProcessor` (`app/services/subagent/external_payment_processor.rb`): накопительный платёж `PaymentProcessor::ExternalProcessor` (`app/apis/payment_processor/external_processor.rb`) и `DepositTransaction` на каждое списание или возврат. Перед списанием проверяет только `has_debt?`, превышение суммы над долгом не проверяет. После списания вызывает `mark_paid!`, если `may_mark_paid?`.
- Возврат денег менеджером по субагентскому заказу: `Payment#refund!`/`#refund_detailed!` → `#outer_partner_refund!` (`app/models/payment.rb:619`) → `mark_refunded!`, `DepositTransaction(refund)`, вебхук `refund` (`Order::ExternalNotificationSerializer.refund_notification`, `app/services/order/external_notification_serializer.rb:231`, только `order_id`, `timestamp`, `request_reference`, `amount`).
- Доступ к методам PAPI задаётся пресетами партнёра (`access_presets`, правила `controller => [methods]`), см. `spec/controllers/papi/context.rb`.

### PartnerBonus и B2C-мили

- `PartnerBonus` (`app/models/partner_bonus.rb`): `kind` только `alfa_miles` (стр. 6), статусная машина под API Альфы (стр. 11), `amount > 0` (стр. 19), `applied?` = `created? || confirmed?`.
- Таблица `partner_bonuses`: `kind`, `status`, `amount` (integer), `order_id`, `external_id`, `metadata` (json), `confirmed_at`, `refunded_at`.
- `Order has_one :partner_bonus` (`app/models/order.rb:291`).
- Всё, что ходит в Альфу или выгружает мили, проверяет `alfa_miles?` или `kind = 'alfa_miles'` точным совпадением:
  - hold в `Papi::V3::OrdersController#create` (стр. 167–172);
  - `Order#confirm_partner_bonus`/`#refund_partner_bonus` (стр. 4196, 4202);
  - `Payment` → `SyncTransactionWorker` (`app/models/payment.rb:520`);
  - `OrderLog#sync_with_alfa_miles` (`after_create_commit`, `if: has_alfa_miles_bonus?`);
  - реестр для Альфы `PartnerBonuses::AlfaMiles::GenerateReportEntries` и `alfa_miles_report_entries`;
  - выгрузка в 1С `Accounting::AlfaMilesPayments`;
  - `tour_end_alfa_miles_agg` (`app/services/accounting/repo/tour_end_exportable.rb:290`).
- Путь создания заказа:
  - `partner_bonuses` входит в `OrderCreation::EXTERNAL_ORDER_PARAMS`;
  - `Order#build_benefits` → `#build_requested_partner_bonus` (стр. 4065) → `PartnerBonuses::RedemptionValidator`. Валидатор пропускает **любой** `kind` из enum (`kind_supported?`), проверяет «1 ₽ остаётся» и баланс клиента в Альфе только для `alfa_miles`.
- Флаг партнёра `alfa_miles_enabled` — boolean-колонка `partners` (`default: false, null: false`), входит в список атрибутов `Partner` (`app/models/partner.rb:98`), подпись в `config/locales/ru.yml:3586`.
  - Показывается в админке: `app/admin/partners.rb:158`, `app/views/admin/partners/_form.html.haml:281`.
  - Отдаётся наружу в настройках партнёра:
    - `Partner::SettingsWebSerializer` → `Papi::V3::PartnerController#settings` (WL на вебе);
    - `Partner::SettingsSerializer` → `#wl_settings` (WL в мобильном приложении) и `ApplicationController` (стр. 1064).

    Судя по названию, по нему фронт показывает переключатель списания миль.
  - Бэкенд при создании заказа флаг не проверяет: `RedemptionValidator` смотрит только на `kind`.
  - На 27.10.2026 флаг включён только у партнёра 1220 `alfa_travel` (WL). Бонусов `alfa_miles` у заказов без партнёра всего 2, февраль–март 2026.
- Прецедент вывода колонки из употребления: `Coupon` (`self.ignored_columns = LEGACY_COLUMNS`, `app/models/coupon.rb:35`).
- Админка `PartnerBonus` (`app/admin/partner_bonuses.rb`): `index`/`show`, панели платежей и request logs, действия только для `alfa_miles`.
- Менеджерка показывает скидку типа `partner_bonus` как «АльфаМили» (`app/assets/javascripts/manager/models/order.coffee:236`).
- Лог B2C-миль: `PartnerBonuses::AlfaMiles::Utils::Logger` → `order.log("[АльфаМили] ...", :info, 0, nil, action_code: :alfa_miles)`. Каждый `OrderLog` на `after_create` вызывает `make_notify` → `Order::ExternalNotification::Sender`.

### Скидка, цена и комиссия

- Скидка заказа одна: `Order#discount` (стр. 2063). Приоритет: сертификат LT → купон → кешбэк (`bonuses_granted`) → `partner_certificates` → `partner_bonus` → промокод МГТ. Для `partner_bonus`: `[partner_bonus_amount, base_price - 1].min`, то есть «1 ₽ деньгами» и тихое обрезание.
- `Order#partner_bonus_amount` (стр. 2119): `amount` бонуса, если `new_record?` или `applied?`, иначе 0.
- `price = base_price - discount[:price]` (стр. 1757), `full_price = price + markup` (стр. 1747), `remaining_amount = full_price - paid_amount` (стр. 1881). `#discount_price` (стр. 1644) распределяется по позициям в `LineItemsV2::Advanced::PriceCalculator`.
- Комиссия партнёра:
  - `Partner#order_commission` (`app/models/partner.rb:580`) = `partner_price × ставка`;
  - `Order#partner_price = package.net_price - bonuses` (стр. 1302–1317). `package.net_price` — клиентская цена пакета без допуслуг;
  - результат лежит в `partner_checks` (`Order#generate_partner_check!`, стр. 1261). Пересчёт: `after_create`, переход в `confirmed`, изменение `net_price` пакета, замена пакета или партнёра;
  - используется в отчётах партнёру (`AffiliateReports`, `PartnerStatistics`, выгрузки конверсий, PAPI v2 reports). В 1С-выгрузках не найдена.
- `Order#update_stat_prices` — `after_commit` самого заказа (стр. 438, 4438): пишет `stat_price`/`stat_base_price` и `order_price_changes`. При изменении только `PartnerBonus` не срабатывает. B2C обновляет финданные явно: `HoldOrder#refresh_order_financial_data!` (`app/services/partner_bonuses/alfa_miles/hold_order.rb:104`) — `stat_price`, `stat_base_price`, `generate_partner_check!(true)`.
- Оценка штрафа при отмене для клиента (`cancellation_refund_data`) считается от `order.full_price` (`CancellationPolicy::Stage#define_price`, `app/models/cancellation_policy/stage.rb:100`), то есть уже за вычетом скидки.

### Прочее

- Поступления на депозит: `DepositTransactions::CreateFromAlfaAccountTransactions` сопоставляет платежи TravelSolutions по ИНН и маскам назначения «Оплата Обеспечительного платежа по п. 6.1.» и «Оплата по заказу».
- Документация PAPI: `docs/papi/v3/controllers/orders/3.0.yml`. Ручка `certificate` описана в базовой версии (стр. 136), так как в коде она не версионируется. Правила — `docs/papi/v3/README.md`.

## Scenarios

Пример: стоимость заказа (`base_price`) 100 000 ₽, у партнёра включены мили.

1. **Первое списание.** Заказ создан, долг 100 000. `debit 30 000`: создаётся `PartnerBonus(partner_alfa_miles, confirmed, amount 30 000)` и операция `debit 30 000, balance_after 30 000`. Цена заказа и `stat_price` — 70 000, долг 70 000, комиссия в `partner_checks` пересчитана от базы за вычетом миль. В логе заказа запись об операции. Ответ: остаток 30 000, цена 70 000, долг 70 000.
2. **Оплата остатка.** `/payments paid 70 000`: долг 0, заказ в `paid`. Поведение `/payments` не меняется.
3. **Повтор запроса.** Тот же `operation_id` с теми же параметрами: 200, данные исходной операции, ничего не меняется.
4. **Конфликт ID.** Тот же `operation_id` с другими параметрами или на другом заказе: 409 `operation_conflict`, ничего не меняется.
5. **Допуслуга.** Добавлен трансфер на 5 000, долг 5 000. `debit 5 000`: остаток 35 000, цена 65 000, долг 0. Либо партнёр платит 5 000 через `/payments`.
6. **Списание больше долга.** `debit`, когда долг меньше суммы, в том числе если заказ уже оплачен деньгами полностью: 422 `amount_exceeds_debt`.
7. **Нарушение правила 1 ₽.** `debit`, после которого остаток превысит `base_price − 1`: 422 `amount_exceeds_limit`.
8. **Частичный возврат миль на активном заказе.** Оплачено 70 000 деньгами и 30 000 милями. `refund 10 000`: остаток 20 000, цена 80 000, долг 10 000, комиссия пересчитана. Партнёр доплачивает 10 000 через `/payments`.
9. **Возврат больше остатка.** `refund` больше остатка или по заказу без бонуса этого `kind`: 422 `amount_exceeds_balance`.
10. **Отмена с полным возвратом денег.** Менеджер вернул 70 000 (вебхук `refund`). Партнёр шлёт `refund 30 000`, остаток 0. Алерта нет.
11. **Отмена со штрафом 100%.** Менеджер ничего не возвращает. Партнёр `refund` не шлёт, остаток 30 000 — долг партнёра.
12. **Возврат миль без возврата денег.** На заказе в `canceled`/`annulled` возврат миль, а денег по заказу не возвращали: операция выполняется, в лог заказа пишется предупреждение и уходит сообщение в Sentry.
13. **Списание на отменённом заказе.** `debit` на заказе в `canceled`/`annulled`: 422 `order_canceled`.
14. **Другая скидка на заказе.** У заказа есть купон, сертификат LT, кешбэк, партнёрские сертификаты, промокод МГТ или B2C-бонус `alfa_miles`: 422 `discount_conflict`.
15. **Мили не включены.** `partner_bonus_kind` партнёра пустой или не партнёрский (например, `alfa_miles`): 422 `bonus_not_enabled`.
16. **Ошибки доступа и параметров.** Чужой заказ: 404 `order not_found`. Неверная подпись или параметры: 422 `invalid_params` с ошибками по полям.
17. **Новый `kind` в создании заказа.** `partner_bonuses: { kind: 'partner_alfa_miles', ... }` в `orders#create`/`prebuild`: ошибка `partner_bonuses` (`invalid_kind`), бонус не создаётся.
18. **B2C-мили не затронуты.** `alfa_miles` работают как раньше. Для `partner_alfa_miles` не запускаются hold, подтверждение, возврат и синхронизация с Альфой, реестр для Альфы и выгрузки `alfa_miles`.
19. **Настройки партнёра после миграции.** У партнёра 1220 `partner_bonus_kind = alfa_miles`, и `/papi/v3/partner/settings` и `wl_settings` по-прежнему отдают `alfa_miles_enabled: true`. У партнёра с `partner_alfa_miles` и у партнёров без программы — `alfa_miles_enabled: false`. В админке программа выбирается одним выпадающим списком, значение вне `PartnerBonus.kinds` не сохраняется.

## Implementation decisions

### Учёт миль в заказе

- **Новый `kind`.** В `PartnerBonus` добавляется `partner_alfa_miles`. Заводится общий признак «бонус ведёт партнёр» (набор таких `kind`), чтобы следующая программа добавлялась новым значением enum без правки проверок.
- **Статус.** Для партнёрских `kind` статусная машина не используется: бонус создаётся в `confirmed` с `confirmed_at` при первом `debit` и так и остаётся. Источник истины — `amount` и журнал. Для этих `kind` разрешается `amount = 0`. Для `alfa_miles` проверка `amount > 0` остаётся.
- **Скидка.** Работает через существующий путь `partner_bonus_amount` → `discount`/`bonuses`/`partner_price`. Формулы цены не меняются.
- **Пересчёт финданных.** После каждой операции пересчитываются `stat_price`, `stat_base_price` и `partner_checks`, так же как в `HoldOrder`. Эта логика выносится в общий переиспользуемый кусок, им пользуются и B2C, и новая ручка.
- **Путь создания заказа.** `RedemptionValidator` отклоняет партнёрские `kind` с ошибкой `invalid_kind`: в `orders#create`/`prebuild` принимается только `alfa_miles`.

### Журнал операций

Новая таблица `partner_bonus_operations`. Записи только добавляются, исправление — новой операцией.

| Колонка | Тип | Примечание |
|---|---|---|
| `id` | bigint | |
| `partner_bonus_id` | bigint, not null | |
| `order_id` | integer, not null | дубль для сверки без join |
| `partner_id` | integer, not null | дубль для сверки по партнёру |
| `operation_type` | string, not null | `debit`, `refund` |
| `amount` | integer, not null | > 0, рубли |
| `balance_after` | integer, not null | остаток миль после операции |
| `external_id` | string, not null | `operation_id` партнёра |
| `created_at`, `updated_at` | datetime | `created_at` = дата операции для сверки |

Индексы: уникальный `(partner_id, external_id)`; `(partner_bonus_id)`; `(partner_id, created_at)`.

`PartnerBonus has_many` операций. Флаги второго этапа (`verified`, `cleared`, привязка к реестру) лягут на операции или строки реестра, не на `PartnerBonus`: реестр может согласовать только часть операций заказа.

### Доступ партнёра

- **Селектор программы.** Новая колонка `partners.partner_bonus_kind` (string, nullable): значение из `PartnerBonus.kinds` или `NULL`, у партнёра не больше одной программы. Валидация на включение в `PartnerBonus.kinds`. В админке партнёра — выпадающий список с пустым вариантом и подписями из I18n («АльфаМили (B2C)», «АльфаМили партнёра»). Он заменяет чекбокс `alfa_miles_enabled`.
- **Совместимость API.** `alfa_miles_enabled` в `Partner::SettingsSerializer` и `Partner::SettingsWebSerializer` остаётся тем же полем, но вычисляется: `partner_bonus_kind == 'alfa_miles'`. Фронты и мобильное приложение изменений не видят.
- **Вывод `alfa_miles_enabled` в два релиза:**
  - первый: добавить `partner_bonus_kind`, заполнить `alfa_miles` там, где `alfa_miles_enabled = true` (на 27.10.2026 это только 1220), перевести весь код на селектор, `alfa_miles_enabled` — в `ignored_columns` `Partner`;
  - второй, отдельной задачей: удалить колонку `alfa_miles_enabled`. Если удалить её сразу, старые поды во время выката будут обращаться к удалённой колонке.
- **`kind` в запросе не передаётся.** Ручка берёт его из `partner_bonus_kind`, если это партнёрский `kind`; для заказа, у которого бонус уже есть, — из самого бонуса.
- Если у партнёра позже появится несколько программ, добавим необязательное поле `kind`. Подпись строится через `sha256_chain_signature` с `compact`, поэтому без этого поля она совпадёт со старой, и текущая интеграция не сломается.
- В PAPI-пресет партнёра добавляется метод `partner_bonus` контроллера `orders`.

### Ручка `POST /papi/v3/orders/:id/partner_bonus`

Живёт в `OrderSubagentMethods` с теми же `set_token`, `set_notifiable_order`, `dry_validate` и `log_request`, что `certificate` и `payments`.

Параметры:

| Поле | Тип | Обяз. | Описание |
|---|---|---|---|
| `operation` | string | да | `debit` — списание миль, `refund` — возврат миль |
| `amount` | integer | да | ≥ 1, рубли |
| `operation_id` | string | да | уникальный ID операции у партнёра, до 255 символов |
| `signature` | string | да | `SHA256(SHA256(order_id) + SHA256(operation) + SHA256(amount) + SHA256(operation_id) + SHA256(partner_api_key))` |

Обработка, всё под `Order.lock` в одной транзакции:

1. **Идемпотентность.** Ищем операцию по `(partner_id, operation_id)`. Если найдена с тем же заказом, `operation` и `amount`, отвечаем 200 её данными и текущим состоянием заказа. Если найдена с другими параметрами — 409 `operation_conflict`.
2. **Проверки:**
   - `partner_bonus_kind` партнёра — партнёрский `kind` (он и применяется);
   - для `debit`:
     - статус заказа не `canceled`/`annulled`;
     - тип скидки заказа пустой или `partner_bonus`, и существующий бонус того же `kind`;
     - `amount ≤ remaining_amount`;
     - `остаток + amount ≤ base_price − 1`;
   - для `refund`: бонус этого `kind` есть и `amount ≤ остаток`.
3. **Запись.** Находим или создаём `PartnerBonus`, меняем `amount`, создаём операцию с `balance_after`.
4. **Финданные.** Пересчитываем `stat_price`, `stat_base_price` и `partner_checks`.
5. **Лог заказа.** Пишем операцию, сумму, `operation_id` и остаток.
6. **Мягкий алерт.** `refund` на заказе в `canceled`/`annulled`, по которому деньги не возвращались (сумма возвратов по платежам 0): предупреждение в лог заказа и `Sentry.capture_message` с `order_id`, `operation_id`, суммой. Без блокировки.
7. **`log_request`** в `ExternalRequestLog`.

Ответ 200:

```json
{
  "success": true,
  "order_id": 374350191,
  "kind": "partner_alfa_miles",
  "operation": "debit",
  "operation_id": "ts-123",
  "amount": 30000,
  "balance": 30000,
  "order": { "price": 70000, "debt": 70000 }
}
```

`balance` — остаток миль на заказе после операции. `order.price` — `full_price`. `order.debt` — `remaining_amount`.

Ошибки, в формате `error!` (`{ success: false, error, errors }`):

| HTTP | `error` | Когда |
|---|---|---|
| 400 | `Authorization token error` | нет ключа партнёра (существующее поведение `set_token`) |
| 404 | `order not_found` | заказ не принадлежит партнёру |
| 422 | `invalid_params` | валидация полей или подписи, ошибки по полям в `errors` |
| 422 | `bonus_not_enabled` | у партнёра не выбрана партнёрская программа в `partner_bonus_kind` |
| 422 | `order_canceled` | `debit` на `canceled`/`annulled` |
| 422 | `discount_conflict` | у заказа другая скидка |
| 422 | `amount_exceeds_debt` | `debit` больше долга |
| 422 | `amount_exceeds_limit` | после `debit` остаток превысит `base_price − 1` |
| 422 | `amount_exceeds_balance` | `refund` больше остатка или бонуса нет |
| 409 | `operation_conflict` | `operation_id` уже использован с другими параметрами |

Документация ручки — в базовом контракте `orders` (3.0) рядом с `certificate`, в том же PR. В описание входят правила для партнёра:

- порядок «мили → `/payments` на остаток»;
- при отмене возвращать мили только после нашего вебхука `refund` на всю оплаченную деньгами сумму;
- снижение цены на активном заказе мы возвращаем деньгами;
- замена уже оплаченных денег милями не поддерживается.

### Возвраты денег

Без изменений: менеджер возвращает деньги через менеджерку, `outer_partner_refund!` возвращает их на депозит и шлёт вебхук `refund`. Ручка миль статус заказа не меняет: в `paid` его переводит `/payments`, деньгами всегда остаётся ≥1 ₽.

## Testing decisions

- **Хороший тест** проверяет внешнее поведение: ответ ручки, остаток миль, операции журнала, цену и долг заказа, `stat_price`, комиссию в `partner_checks`, запись в логе заказа, сообщение в Sentry. Не проверяет внутренние вызовы сервисов. Стиль — `rspec-style-guide`, `describe`/`context`/`it` по-английски.
- **Controller-спек новой ручки** `Papi::V3::OrdersController#partner_bonus`, по образцу `spec/controllers/papi/v3/orders_controller/payments_spec.rb` (`include_context 'papi'`, подпись через `make_signature`). Покрывает сценарии 1, 3–16. Туда же сквозной сценарий 1→2: мили, затем `payments` на остаток, долг 0, заказ `paid`. И сценарий 8 с доплатой.
- **Модельный спек** `Order` с бонусом `partner_alfa_miles`, по образцу `describe '#partner_bonus_amount'` и проверок `partner_bonuses` при создании в `spec/models/order_spec.rb`:
  - скидка и цена учитывают остаток сразу, остаток 0 скидку не даёт, `partner_price`/комиссия считаются от цены за вычетом миль;
  - события заказа (подтверждение, отмена) и создание `OrderLog` не запускают B2C-воркеры Альфы;
  - `partner_bonuses` с новым `kind` при создании заказа даёт ошибку `invalid_kind` (сценарии 17–18).
- **Настройки партнёра** (сценарий 19): расширить `spec/controllers/papi/v3/partner_controller_spec.rb` (`#wl_settings`) и проверить `#settings` — `alfa_miles_enabled` вычисляется из `partner_bonus_kind`. Плюс модельная проверка `Partner`: значение вне `PartnerBonus.kinds` невалидно. Существующие спеки, которые создают партнёра с `alfa_miles_enabled: true` (например, `spec/models/order_spec.rb`), переводятся на `partner_bonus_kind: 'alfa_miles'`.
- **Регрессия.** Без изменений проходят существующие спеки B2C-миль: `spec/services/partner_bonuses/**`, `spec/workers/partner_bonuses/**`, части `spec/models/order_spec.rb` про партнёрские бонусы, `spec/services/accounting/repo/tour_end_exportable_alfa_miles_spec.rb`, `spec/controllers/papi/v3/orders_controller/payments_spec.rb`.

## Out of scope

- Второй этап: реестры, флаги `verified`/`cleared`, учёт поступления денег, выгрузки в 1С (`tour_end`, `daily_payments`), правило депозита для поступлений по реестру.
- Мили в `orders#create`/`prebuild`.
- Интерфейс менеджера для миль: ручные корректировки, разбивка возврата на деньги и мили, мили в вебхуках партнёру.
- Замена уже оплаченных денег милями (`debit` больше долга).
- Оплата милями на 100%.
- Частичные возвраты при отмене — вручную через поддержку.
- Обнаружение случая, когда цена заказа упала ниже остатка миль. Скидка в нём молча обрежется до `base_price − 1`, и долг партнёра разойдётся со скидкой. Это известный риск, следить за ним на втором этапе.
- Корректность клиентской оценки штрафа (`cancellation_refund_data`) по заказам со скидкой.
- Проверка при создании заказа, что `partner_bonuses.kind` совпадает с `partner_bonus_kind` партнёра. Для B2C это изменение поведения, его делаем отдельной задачей.
- Удаление колонки `alfa_miles_enabled` — следующий релиз, отдельная задача.

## Further notes

- **Выкатка:**
  - миграции: `partner_bonus_operations`, `partners.partner_bonus_kind` с заполнением из `alfa_miles_enabled`;
  - проверить после деплоя, что у 1220 `partner_bonus_kind = alfa_miles` и WL Альфы по-прежнему показывает мили;
  - выставить `partner_bonus_kind = partner_alfa_miles` партнёру 1340;
  - добавить `partner_bonus` в PAPI-пресет TravelSolutions;
  - передать TravelSolutions документацию с правилами возврата.
- **Канал алерта.** Пока лог заказа и Sentry. Если менеджерам нужен отдельный канал (задача в заказе, отчёт), решаем после первых случаев.
- **Лог заказа и вебхуки.** Записи о милях пишутся через `order.log`, а `OrderLog` на `after_create` вызывает `make_notify`. При реализации проверить, не уйдут ли эти записи вебхуком партнёру.
- **Отклонённые альтернативы:**
  - мили как оплата через `paid_amount`: бизнес согласился на скидку с уменьшением комиссии;
  - мили в `orders#create`: около 40% заказов TravelSolutions отменяются без оплаты, цена может смениться при конкретизации, общий флоу создания завязан на B2C;
  - мили как `Payment`: фискализация, депозит, банковская сверка `verify!`;
  - `alfa_miles_report_entries` как журнал: это исходящий реестр для Альфы, одна покупка и один возврат на бонус;
  - `has_many :partner_bonuses`: ломает `has_one` по всему коду;
  - API с абсолютной суммой, как в `certificate`: нет ID операций для сверки, гонки;
  - обязательный `kind` в запросе: выбирать не из чего (одна программа на партнёра, один бонус на заказ), а необязательное поле можно добавить позже без поломки подписи.
- **Подтверждения бизнеса** (26–27.10.2026): долг партнёра = остаток миль на заказе; комиссия уменьшается на мили; TravelSolutions присылает мили после создания заказа.
