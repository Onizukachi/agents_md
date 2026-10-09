# LT-54688 — Промокоды Мосгортура через PromoService

## Problem

У Мосгортура (МГТ) есть свой сервис промокодов PromoService. Он проверяет промокод, считает скидку,
резервирует лимит использований и фиксирует применение после оплаты. Заказы он не создаёт и платежи не
проводит.

Клиент вайтлейбла гибридного субагента МГТ должен иметь возможность ввести промокод МГТ на чекауте и
получить скидку. Применение промокода должно корректно пройти весь путь заказа: создание, оплату, отмену.
Сейчас поле промокода на WL понимает только наши купоны (`Coupon`), а промокоды МГТ мы никуда не
передаём.

Скидки по промокодам МГТ войдут во взаиморасчёты с МГТ. Поэтому нам нужно хранить у себя, какой промокод,
на какую сумму и когда применён и отменён. Ещё нужен способ вручную разобрать и повторить операцию, если
автоматика не сработала.

## Solution

У партнёра появляется настройка **провайдер промокодов** с двумя значениями: наш (по умолчанию) и МГТ.
Показывать ли поле промокода вообще, по-прежнему решает существующий флаг `enable_coupon`. Фронт ничего
не знает о провайдере: промокод приходит в том же `coupon_code`, маршрут выбирает бэкенд по партнёру
заказа. Ошибки отдаются под тем же ключом, что ошибки купона. Шаг оплаты WL сейчас рисует legacy-фронт
этого репозитория. Там нужна одна правка: кнопка у применённого промокода МГТ должна называться «Отменить
промокод», как у купона.

Для партнёра с провайдером МГТ промокод проходит цепочку PromoService:

- **Validate** на `prebuild` и на `create`. Скидка показывается клиенту так же, как скидка по купону.
  Если МГТ отказал или недоступен, клиент видит ошибку у поля промокода, а заказ не создаётся.
- **Hold** сразу после сохранения заказа. Скидка заказа от исхода Hold не зависит. Если Hold не прошёл,
  скидка остаётся, а при техническом сбое Hold повторяется в фоне. Оплата не блокируется.
- **Confirm** после первой успешной оплаты. Передаются фактические суммы заказа и время оплаты.
  Подтверждения тура туроператором не ждём.
- **Cancel** при отмене заказа (`cancel`, `cancel_by_client`). Если подтверждения ещё не было, холд
  снимается через `UserCancellation`. Если было — возврат через `FullRefund`. Аннуляция промокод не
  трогает.

Каждый вызов PromoService пишется в отдельную таблицу логов. Для ручного разбора есть страница в
ActiveAdmin без проверок ролей: список применений, карточка с логами и действия «Hold»,
«Confirm», «Снять холд», «Вернуть».

## Current system state

### PromoService МГТ (по документации и проверке на бою 06–07.10.2026)

- **Базовый адрес и авторизация.** Base URL `https://mt.mosgortur.ru/PromoService`. Авторизация
  заголовком `Authorization: ApiKey <key>`. `ClientId`, `SourceSystem` и `FlowMode` привязаны к ключу, в
  запросах их не передаём. Тестовой среды нет, тесты идут на бою тестовыми промокодами
  (`LT_TEST_FIXED_500`, `LT_TEST_PERCENT_10`, `LT_TEST_PERCENT_CAP_10`).
- **Эндпоинты:** `POST /api/v1/promocodes/{validate,hold,confirm,cancel}`, `GET /health/{live,ready}`.
- **Ответы.**
  - Бизнес-ошибки приходят с HTTP 200: `isApplicable`/`isHeld`/`isConfirmed`/`isCancelled` = false,
    `reasonCode`, `message` по-русски. 401/403 — ключ, 503 — временная недоступность с `Retry-After`.
  - Время в ответах с 7 знаками дробной секунды.
  - Суммы дробные. `calculationToken` — подписанная строка около 1,7 КБ.
- **Validate** (`promoCode`, `fullPrice`, `netPrice`, `currency: RUB`).
  - Возвращает `calculationId`, `discountAmount`, `finalPrice`, `calculationToken`, `expiresAt`. Расчёт
    живёт 15 минут.
  - Процент считается от `fullPrice`: при `fullPrice` 10000 и `netPrice` 8000 скидка 10% = 1000.
  - Лимит Validate не расходует.
- **Hold** (`calculationToken`, `checkout {sourceSystem: PROTOUR, externalId}`, `externalEventId`).
  - Возвращает `usageId`, `status: Held`, `expiresAtUtc`. Холд живёт 1 час, МГТ согласился поднять до
    24 часов.
  - Повтор с тем же расчётом и оформлением возвращает тот же `usageId`.
  - Hold по истёкшему расчёту возвращает `CALCULATION_EXPIRED`.
- **Confirm** (`calculationToken`, `order {sourceSystem: PROTOUR, externalId}`, `paymentOccurredAt` с
  поясом, `fullPrice`, `netPrice`, `discountAmount`, `finalPrice`, `currency`, `externalEventId`).
  - Возвращает `isConfirmed`, `usageId`, `calculationId`, `status`, `calculatedAmounts`,
    `actualAmounts`, `moneyDelta`, `anomalies`.
  - Окно подтверждения — 365 дней от выпуска расчёта.
  - Без Hold подтверждается с аномалией `MissingHold`.
  - Если скидка отличается от расчёта — подтверждается с аномалией `AppliedDiscountMismatch`.
  - Если выросла цена при той же скидке — подтверждается без аномалий, разница видна только в
    `moneyDelta`.
  - Если `paymentOccurredAt` раньше выпуска расчёта (с точностью до долей секунды) — отказ
    `INVALID_PAYMENT_TIME`.
  - Повтор с тем же `externalEventId` после бизнес-отказа и с исправленными данными проходит: отказы не
    кэшируются.
  - Повтор после успеха возвращает существующее подтверждение.
  - Если холд истёк до оплаты, подтверждение проходит с аномалией `LatePayment` (проверено 07.10.2026), а
    если лимит уже занят — по словам поддержки, ещё и с `OverLimit`.
- **Cancel** (`usageId`, `reason`, `externalEventId`).
  - По `Held` принимается только `UserCancellation`; на `FullRefund` приходит
    `INVALID_CANCELLATION_REASON`.
  - По `Confirmed` принимаются обе причины.
  - Повтор с тем же `externalEventId` возвращает исходный результат.
  - Отмена уже отменённого применения с другим `externalEventId` возвращает `IDEMPOTENCY_CONFLICT`.
- **Поля условий кампаний.** Токен показывает, что сервис умеет учитывать продукт, направление, период,
  оператора, отель, клиента и компанию. Мы эти поля не передаём.

### Чекаут и скидки в заказе

- `Papi::V3::OrdersController#prebuild`/`#create` → `build_order` → `Order.build_order`
  (`app/models/concerns/order_creation.rb:289`) → `Order#build_benefits`
  (`app/models/order.rb:2294`, вызывается из `order_creation.rb:441`). Кроме PAPI v3, `Order.build_order`
  вызывает только `CertificateCreator` (подарочные сертификаты).
- `coupon_code` входит в `OrderCreation::EXTERNAL_ORDER_PARAMS` (`order_creation.rb:16`). Наш купон
  применяется через `Order#apply_coupon_code` (`order.rb:1959`) и проверяется в
  `validate :coupon_fits_conditions?` (`order.rb:368`).
- `build_benefits` делает скидки взаимоисключающими: бонусы, купон, лояльность, сертификаты МГТ
  (`mosgortur_certificates`) и partner bonus (альфамили).
- Цепочки суммы скидки:
  - `Order#discount` (`order.rb:2044`) — тип и сумма скидки, их отдают
    `app/views/papi/v3/orders/prebuild.json.jpbuilder:13-14` и `_order.json.jbuilder:19-20`
    (`discount_price`, `discount_type`).
  - `Order#discount_price` (`order.rb:1628`) — её читает распределение скидки по позициям чека
    (`LineItemsV2::Advanced::PriceCalculator`).
  - `Order#bonuses` (`order.rb:1291`).
- Аналог для партнёрских скидок — `partner_certificates_amount` (`order.rb:2080`) и
  `partner_bonus_amount` (`order.rb:2089`).
- После `prebooking` в `create` цена конкретизируется: `concretize_order_price`
  (`app/controllers/papi/v3/orders_controller.rb:606`). Если цена изменилась, сертификаты МГТ
  пересчитываются (`Order#rebuild_mosgortur_certificates`, `order.rb:2357`), а ошибка пересчёта
  останавливает `create`.
- Холд альфамилей ставится синхронно после сохранения заказа (`orders_controller.rb:164-169`), при
  сбое повтор уходит в воркер.
- Цены:
  - `Order#base_price` (`order.rb:1544`) = `package.full_price` + `visa_debt` + допуслуги.
  - `Package#full_price` (`app/models/package.rb:495`) = `net_price` + `fuel_charge`.
  - `Order#price_without_discount` = `full_price` + скидка, где `full_price` включает `markup`
    оплаченных платежей (`order.rb:668`).

### Фронт чекаута WL на проде (проверено 07.10.2026)

- Шаг `/packages/:id/pay` на WL-доменах отдаёт Rails (`packages#show`, `config/routes.rb:998-1002`) с
  legacy-бандлом `package_checkout` из `client/lt-modules` (`webpack/common.config.ts:14`).
  `https://bestbenefits.level.travel/packages/…/pay` грузит
  `assets.cdn.level.travel/assets/package_checkout.*.prod.js` в `#checkout_page`, Next.js там нет.
- Поле промокода (`components/Payment/Discount`) появляется по способу `coupon` из `discount_methods`. Код
  уходит в `coupon_code` на `prebuild`/`create`, ошибки берутся из `order_errors.coupon`.
- После применения скидки (кроме подарочного сертификата) показывается плашка `AppliedCashbackOrPromo`:
  «Промокод активирован», экономия, цена до и после. Кнопка на плашке всегда снимает скидку
  (`addCoupon(null)`), но подпись выбирается по `discount_type`: `bonus` → «Отменить кешбэк», `coupon` →
  «Отменить промокод», любой другой тип → «Активировать». Так уже сейчас выглядят `partner_bonus` и
  `partner_certificates`.

### Фронт `lt-frontend` (`origin/develop` на 06.10.2026)

- **`apps/leveltravel`, шаг `/packages/:id/pay`.** Блок скидок `checkoutPayment/ui/CheckoutDiscount`
  рисуется по `discount_methods` из ответа `prebuild`. Бэкенд кладёт туда способ `coupon` для LT и для
  WL-партнёра с `enable_coupon` (`app/models/order.rb:3084-3099`).
  - Ввод промокода (`PromocodeForm`): `setCouponAndBonuses({ couponCode })`, затем повторный `prebuild` с
    `coupon_code` из корзины. Тот же `coupon_code` из корзины уходит в `create`.
  - Ошибки: `prebuild` кладёт `order_errors` в стор (`features/buildOrder/model/thunks.ts:355`). Если есть
    ключ `coupon`, код сбрасывается из корзины, а `PromocodeForm` показывает тексты из
    `order_errors.coupon` под полем. Бэкенд кладёт туда ошибки купона: `errors.add(:coupon, …)` в
    `Order#coupon_fits_conditions?` и `Coupons::CouponChecker#add_errors_to_order!`.
  - Успех: при непустом `discount_type` вместо формы показывается `DiscountSuccessForm` — «Промокод
    активирован», экономия `discount_price`, цена до и после, кнопка «Не использовать промокод»
    (сбрасывает код и делает `prebuild`). Отдельно обрабатываются только `bonus` и `certificate`, любой
    другой тип выглядит как промокод.
  - `discount_type` и `price_info[].price_id` в typia-типах `lt-api` — строки, новые значения валидацию
    не ломают.
- **`apps/wl`.** Есть страница пакета (`prebuild` только для цены, `routes/package/model/cart/listeners.ts`)
  и туристы. Шага `pay` с блоком скидок, `create` заказа и обработки `order_errors` нет. В корзине есть
  `coupon_code`, но он всегда `null`. Агентский чекаут (`routes/agentCheckout`) скидочных форм не имеет
  намеренно (его README).

### Жизненный цикл заказа

- `mark_paid` (`order.rb:491`) — переход approved/cooling → paid, срабатывает один раз на первой оплате.
  Оплата со стороны МГТ у гибридного субагента тоже приходит сюда:
  `Subagent::ExternalPaymentProcessor` → `mark_paid_and_log`.
- `cancel` (`order.rb:551`) вызывает `refund_partner_bonus`. `cancel_by_client` (`order.rb:574`)
  и `annul` (`order.rb:566`) возврат партнёрских бонусов не вызывают.
- У платежа есть `frozen_at` (время заморозки средств при двухстадийной оплате, `payment.rb:537`) и
  `captured_at`.
- `OrderCancellationWorker` отменяет неоплаченные `approved`-заказы старше суток.

### Партнёр

- Партнёры МГТ: `PartnerIds::MOSGORTUR_ID = 1297`, `MOSGORTUR_WL_ID = 1336`. Признак гибридного
  субагента — `is_subagent_hybrid`.
- `enable_coupon` включает поле промокода на WL (`order.rb:3098`).
- Партнёрские настройки — обычные колонки в `partners`.
- Как добавлять такую настройку, видно по `alfa_miles_enabled`:
  - `ADMIN_PERMITTED_ATTRIBUTES` (`app/models/partner.rb:84-104`);
  - форма `app/views/admin/partners/_form.html.haml`;
  - карточка `app/admin/partners.rb`.

### Прецеденты

- **Альфамили** — `PartnerBonus`:
  - статусы-enum;
  - воркеры `app/workers/partner_bonuses/alfa_miles/` (queue `high`, `retry: 2`);
  - ActiveAdmin `app/admin/partner_bonuses.rb` под ролью `admin_partner_bonuses` с member actions,
    которые синхронно выполняют воркер (`perform_worker`);
  - даты `confirmed_at`/`refunded_at` добавлены отдельной миграцией и бэкфилльнуты из логов для отчёта.
- **Сертификаты МГТ:**
  - клиент `PartnerCertificates::Clients::Mosgortur` на `ExternalRequest`;
  - собственная таблица логов `partner_certificate_logs` (`request`/`response` json);
  - модель `PartnerCertificate`.
- **Внешние HTTP** — только через `ExternalRequest` (`.agents/docs/invariants.md`).

## Scenarios

1. Партнёр с провайдером «наш», клиент вводит промокод — работает как сейчас, через `Coupon`.
2. Партнёр с провайдером МГТ, `prebuild` с действующим промокодом — Validate, в ответе `discount_price` и
   `discount_type: mosgortur_promo`, холда нет.
3. Партнёр с провайдером МГТ, `prebuild` с промокодом, который МГТ отклонил (`PROMOCODE_NOT_FOUND`,
   `LIMIT_EXHAUSTED`, `CAMPAIGN_EXPIRED` и т. п.) — ошибка в `order_errors.coupon` с понятным текстом по
   `reasonCode`, скидки нет.
4. PromoService недоступен (таймаут, 5xx, 401/403) на `prebuild` или `create` — ошибка «не удалось
   проверить промокод, попробуйте позже или оформите без него», заказ не создаётся.
5. `create` с действующим промокодом — Validate по ценам после конкретизации, заказ сохраняется со
   скидкой, сразу ставится Hold (`checkout.externalId` = номер заказа), статус `held`.
6. `create`, МГТ отклонил Validate — заказ не создаётся, ошибка у поля промокода.
7. `create`, Hold упал технически — заказ со скидкой, статус `pending`, Hold повторяется в фоне с тем же
   `externalEventId`. Оплата доступна.
8. `create`, Hold отклонён по бизнес-причине — заказ со скидкой, статус `pending`, без повторов, отказ
   виден в логах.
9. Первая успешная оплата (`mark_paid`) заказа в статусе `held` или `pending` — Confirm.
   - Суммы: `fullPrice` = `base_price`, `netPrice` = `package.net_price`, `discountAmount` = скидка,
     `finalPrice` = разница.
   - `paymentOccurredAt` = `frozen_at || captured_at` первого оплаченного платежа.
   - Статус `confirmed`, сохраняются `usage_id`, `anomalies` и `confirmed_at`.
10. Confirm с аномалиями (`MissingHold`, `LatePayment`, `OverLimit`, `AppliedDiscountMismatch`) —
    применение подтверждено, аномалии сохранены.
11. Confirm отклонён по бизнес-причине или упал технически — статус остаётся прежним. Технический сбой
    повторяется в фоне, бизнес-отказ разбирают вручную в админке и повторяют с тем же
    `externalEventId`.
12. Оплата без промокода МГТ, а также последующие оплаты — к МГТ ничего не уходит.
13. `cancel` или `cancel_by_client` заказа в статусе `held` — Cancel `UserCancellation`, статус
    `cancelled`, `cancelled_at`.
14. `cancel` или `cancel_by_client` заказа в статусе `confirmed` — Cancel `FullRefund`, статус
    `refunded`, `cancelled_at`.
15. Отмена заказа в статусе `pending` (холда нет) — закрываем у себя (`cancelled`) без вызова МГТ.
16. Cancel вернул `IDEMPOTENCY_CONFLICT` — считаем применение уже отменённым и ставим соответствующий
    статус.
17. `annul` — промокод не трогаем.
18. Скидка после отмены промокода остаётся в заказе, цена отменённого заказа не меняется.
19. Админка без проверок ролей.
    - Список с фильтрами: статус, заказ, код, дата, наличие аномалий. Карточка с логами.
    - Действия: Hold для `pending`, Confirm для `pending`/`held` при оплаченном заказе, «Снять холд» для
      `held`, «Вернуть» для `confirmed`.
    - Страница доступна любому пользователю админки, отдельной роли не нужно.
20. Каждый вызов PromoService, включая Validate на `prebuild` без заказа, пишется в лог. Ключ в лог не
    попадает.

## Implementation decisions

### Настройка партнёра

- Колонка `partners.promo_code_provider` (string, not null, default `level_travel`) с enum-значениями
  `level_travel` и `mosgortur`.
- Добавляется в разрешённые атрибуты админки, форму и карточку партнёра, плюс локаль.
- Фронту не отдаётся.
- Включение поля промокода по-прежнему решает `enable_coupon`.

### Таблица применений `mosgortur_promo_codes`

| Колонка | Тип | Назначение |
| --- | --- | --- |
| `order_id` | integer, not null, unique index | заказ; партнёр берётся через заказ |
| `code` | string, not null | введённый промокод |
| `status` | string, not null, default `pending` | `pending`, `held`, `confirmed`, `cancelled`, `refunded` |
| `discount_amount` | integer, not null | скидка из Validate, округлённая вниз до рубля; участвует в цене заказа |
| `calculation_token` | text, not null | для Hold и Confirm |
| `calculation_id` | string, not null | идентификатор расчёта у МГТ: основа `externalEventId`, связь с логами, поддержка и сверка |
| `usage_id` | string | из Hold или Confirm, нужен для Cancel |
| `anomalies` | json | аномалии из Confirm |
| `confirmed_at`, `cancelled_at` | datetime | для взаиморасчётов |
| `created_at`, `updated_at` | datetime | |

- Модель `belongs_to :order`, у `Order` — `has_one ... dependent: :destroy`: номер удалённого заказа может
  достаться новому (`Order#generate_id`), и чужое применение не должно к нему прилипнуть.
- Индексы: `order_id` (unique), `code`, `status`, `created_at` — под фильтры админки.
- Что не храним и почему:
  - суммы на момент Validate, сроки токена и холда, `checkout_external_id` (= номер заказа), причину
    отмены (её задаёт статус) — всё это есть в токене, в логах или выводится;
  - `externalEventId` — он детерминированный.
- Статусы:
  - `pending` — Validate прошёл, холда нет;
  - `held` — холд стоит;
  - `confirmed` — подтверждено после оплаты;
  - `cancelled` — холд снят (`UserCancellation`) или закрыт у нас без вызова;
  - `refunded` — возврат после подтверждения (`FullRefund`).

### Таблица логов `mosgortur_promo_code_logs`

- Колонки:
  - `order_id` (integer, nullable, index) — пустой у Validate: он выполняется до сохранения заказа;
  - `calculation_id` (string, nullable, index) — из ответа Validate или из применения; по нему карточка
    промокода находит Validate, который выставил скидку;
  - `operation` (string: validate/hold/confirm/cancel);
  - `http_status` (integer, пустой при сетевом сбое);
  - `request`, `response` (json);
  - `created_at`.
- В `request` пишем только тело запроса, заголовки не пишем.
- `reasonCode`, `usageId` и аномалии читаем из `response`.

### Клиент PromoService

- Живёт в слое внешних интеграций, работает через `ExternalRequest`.
- Ключ берётся из ENV. Base URL — константа.
- Методы `validate`, `hold`, `confirm`, `cancel`. Каждый пишет лог и возвращает разобранный ответ.
- Ответ классифицируется в одно из трёх:
  - успех;
  - бизнес-отказ с `reasonCode` (HTTP 200 с false-флагом);
  - технический сбой (таймаут, сетевой сбой, 5xx, 401/403, невалидный JSON) — повторяемый.
- `X-Correlation-ID` не передаём: запросы у МГТ находятся по `calculationId` и `usageId`, которые есть в логе.
- Тело ответа без JSON перед записью в лог приводится к UTF-8.
- Значения `externalEventId`: `lt-<calculation_id>-hold`, `lt-<calculation_id>-confirm`,
  `lt-<calculation_id>-cancel`.
  - `calculationId` уникален для каждого Validate. Поэтому ID не пересекаются между стендами и продом,
    которые работают с одним ключом и одинаковыми номерами заказов.
  - Один и тот же ID используется и для автоматических ретраев, и для ручного повтора из админки.
- `checkout.externalId` и `order.externalId` равны номеру заказа, `sourceSystem` всегда `PROTOUR`.

### Чекаут

- Маршрутизация живёт в `build_benefits`. Если `coupon_code` присутствует и у партнёра заказа провайдер
  `mosgortur`:
  - вместо поиска `Coupon` делается Validate;
  - при успехе собирается запись `pending` с кодом, скидкой, токеном и `calculation_id`;
  - промокод МГТ взаимоисключается с остальными скидками так же, как купон.
- Validate передаёт `fullPrice` = `Order#base_price`, без наценок за способ оплаты, и `netPrice` =
  `package.net_price`.
- Ошибки Validate добавляются к `coupon`, тем же ключом, что ошибки нашего купона. Поэтому на
  `prebuild` и `create` фронт показывает их у поля промокода и сбрасывает введённый код.
  - Тексты по `reasonCode` берутся из I18n, неизвестный код получает общий текст.
  - Технический сбой даёт отдельный текст «не удалось проверить промокод».
- Скидка в цене — новая ветка с типом `:mosgortur_promo` в цепочках `discount`, `discount_price` и
  `bonuses`. Её сумма — `discount_amount` записи в любом статусе, поэтому после отмены промокода цена
  заказа не меняется.
- Если при конкретизации на `create` изменилась цена, Validate повторяется по новой цене, как сейчас
  пересчитываются сертификаты МГТ. Отказ останавливает `create` с ошибкой промокода.
- Hold выполняется синхронно в `create` сразу после сохранения заказа, рядом с холдом альфамилей.
  - Успех: `held`, сохраняется `usage_id`.
  - Технический сбой: остаётся `pending`, ставится воркер повтора Hold.
  - Бизнес-отказ: остаётся `pending`, без повторов.
  - Оплата не блокируется.
- Отдельной перевалидации перед Hold нет: скидка зашита в токен, а Validate и Hold идут в одном запросе.
- Промокод МГТ принимаем только в чекауте PAPI v3. В другие пути создания заказа маршрутизация не
  встраивается.

### Подтверждение и отмена

- `after_commit` события `mark_paid` ставит воркер Confirm, если у заказа есть запись в статусе `pending`
  или `held`.
  - Суммы берутся из заказа на момент Confirm: `fullPrice` = `base_price`, `netPrice` =
    `package.net_price`, `discountAmount` = `discount_amount`, `finalPrice` = разница.
  - `paymentOccurredAt` = `frozen_at || captured_at` первого оплаченного платежа, с поясом.
  - При `isConfirmed` = true: `confirmed`, `usage_id` (Confirm без холда создаёт применение),
    `anomalies`, `confirmed_at`.
- `after_commit` событий `cancel` и `cancel_by_client` ставит воркер Cancel.
  - `held` → `UserCancellation`, затем `cancelled`.
  - `confirmed` → `FullRefund`, затем `refunded`.
  - `pending` → `cancelled` без вызова МГТ.
  - `IDEMPOTENCY_CONFLICT` трактуется как «уже отменено».
  - Проставляется `cancelled_at`.
- `annul` ничего не делает.
- Если Hold подтвердился в фоне, когда заказ уже отменён, сразу ставится Cancel. Так сделано у
  альфамилей.
- Воркеры — Sidekiq, по образцу воркеров альфамилей (queue `high`, ограниченные ретраи с бэкоффом).
  Ретраятся только технические сбои. Бизнес-отказ пишется в лог и в лог заказа, повторяется вручную.
- События пишутся в лог заказа с отдельным `action_code`.

### Админка

- Ресурс ActiveAdmin без проверок ролей, рядом с «Партнерскими программами лояльности».
- Список: фильтры по статусу, заказу, коду, дате и «есть аномалии».
- Карточка: поля записи (токен обрезан), аномалии, панель логов по заказу.
- Member actions синхронно выполняют операцию и показывают её результат (успех или `reasonCode`), с
  подтверждением:

  | Действие | Для статуса |
  | --- | --- |
  | Hold | `pending` |
  | Confirm | `pending`/`held` при оплаченном заказе |
  | Снять холд | `held` |
  | Вернуть | `confirmed` |

- В менеджерке тип скидки подписан «Промокод МГТ».

### Фронт

- Legacy-чекаут (`client/lt-modules`): кнопка на плашке применённой скидки с типом `mosgortur_promo`
  подписывается «Отменить промокод», как у купона. Других правок нет. Подписи для `partner_bonus` и
  `partner_certificates` не трогаем.
- `lt-frontend`, `apps/leveltravel`: правок нет. Поле, отправка кода, показ скидки (тип `mosgortur_promo`
  выглядит как промокод) и ошибок у поля работают как с купоном.
- `lt-frontend`, `apps/wl`: когда туда переедет шаг оплаты, нужен блок промокода по образцу
  `CheckoutDiscount`:
  - показывать по способу `coupon` из `discount_methods`;
  - класть код в `coupon_code` корзины и делать `prebuild`, отправлять его же в `create`;
  - выводить `order_errors.coupon` под полем и сбрасывать код при ошибке;
  - при ошибке `create` показывать `error` из ответа.

## Testing decisions

- Единственная внешняя граница — HTTP PromoService, она подменяется через WebMock
  (`stub_request` на `mt.mosgortur.ru`). Всё выше работает по-настоящему. Проверяем наблюдаемое
  поведение:
  - ответы PAPI;
  - цену и скидку заказа;
  - статус и поля записи;
  - тела отправленных запросов;
  - записи в логе.
- Три входа:
  1. **Чекаут PAPI v3.** Спеки контроллера `Papi::V3::OrdersController` для `prebuild` и `create`.
     Прецедент — `spec/controllers/papi/v3/orders_controller/subagent_create_spec.rb` и
     `concretize_order_price_spec.rb`. Сценарии 1–8, 20.
  2. **События заказа.** `mark_paid!`, `cancel!`, `cancel_by_client!`, `annul!` с
     `Sidekiq::Testing.inline!`. Сценарии 9–18.
  3. **Админка.** Request-спек ActiveAdmin на member actions и доступ по роли. Сценарий 19.
- Отдельных юнит-спеков клиента и воркеров не пишем.
- Названия `describe`/`context`/`it` пишем по-английски.

## Out of scope

- Поля условий кампаний: продукт, направление, период, оператор, отель, клиент, компания.
- Промокод МГТ вне чекаута PAPI v3: старый `OrdersController#build`, CRM, менеджерка, API-заказы вне
  PAPI v3.
- Блок промокода в `lt-frontend/apps/wl`: появится вместе с переездом туда шага оплаты.
- Подписи кнопки для `partner_bonus` и `partner_certificates` в legacy-чекауте.
- Смена подписи способа оплаты «Промокод или сертификат» для партнёров МГТ.
- Сочетание промокода МГТ с сертификатами МГТ и другими скидками: остаются взаимоисключающими.
- Отмена промокода при аннуляции.
- Частичный возврат: отменяем только при отмене заказа целиком.
- Отчёт или выгрузка для взаиморасчётов с МГТ: данные копятся в таблице, отчёт — отдельная задача.
- Чистка таблицы логов.
- Исправление того, что `cancel_by_client` не возвращает альфамили.

## Further notes

- Ключ API нельзя размещать в репозитории, документации, почте и чатах, это требование МГТ. На
  окружения его заводим через ENV.
- Холд сейчас живёт 1 час, МГТ обещал поднять до 24 часов. Неоплаченные заказы `OrderCancellationWorker`
  отменяет через сутки, так что сроки совпадают. Если холд истечёт до оплаты, Confirm всё равно пройдёт с
  аномалией `LatePayment`.
- Тестовые промокоды на бою ограничены 10 операциями. Неясно, считаются ли это одновременные
  применения или все за время жизни кода. На 07.10.2026 создано 7 применений, все отменены.
- Скидка из Validate округляется вниз до целого рубля: цены заказа целые. Дробный остаток уходит в
  Confirm как фактическая скидка, то есть копеечное расхождение с расчётом.
- Скрипты ручной проверки API лежат вне репозитория (scratchpad сессии 06–07.10.2026).
