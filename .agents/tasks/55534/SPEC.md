# LT-55534 Настройка способа открытия 3DS для партнёра

## Summary

Режим прохождения 3DS при оплате картой сейчас один на всю систему: глобальный флаг `Settings.redirect_3ds_mode?` («Прохождение 3DS в отдельной вкладке»). Нужно дать возможность задавать его для конкретного партнёра независимо от остальных.

В карточке партнёра в админке появляется настройка «Способ открытия 3DS» с тремя вариантами:

- «По общей настройке» — брать значение из `Settings`. Вариант по умолчанию, поведение существующих партнёров не меняется.
- «Во фрейме» — форма подтверждения банка рендерится внутри страницы оплаты.
- «В новой вкладке» — форма подтверждения банка открывается в отдельной вкладке.

Ключевые решения:

- Настройка живёт **в колонке `partners.redirect_3ds_mode`** (строковый enum), а не в Redis-настройке: аудит через `has_paper_trail`, никаких миграций Redis и рассинхрона с карточкой партнёра.
- Решение принимается **одним предикатом `Partner#separate_tab_3ds?`**. Вариант «по общей настройке» внутри него читает `Settings.redirect_3ds_mode?`, поэтому семантика глобального флага не размазывается тернарником по пяти местам вызова.
- Глобальный чекбокс `Settings.redirect_3ds_mode` **остаётся** и означает ровно вариант «По общей настройке».
- Запрет отдельной вкладки для мобильного приложения LT (`app_request?` / `payment.from_app?`) **остаётся безусловным** и приоритетнее выбора партнёра.
- Партнёр для `PaymentController` берётся из **`payment.order.partner`**: запрос приходит от банка, партнёра запроса там нет, а платят за конкретный заказ.
- Это **хотфикс**: paired PR по `leveltravel-hotfix-workflow` (сначала в `master`, затем cherry-pick в `develop`).

## Problem

`Settings.redirect_3ds_mode?` читается в пяти местах, и режим нельзя включить выборочно:

| Место | Что отдаёт |
|---|---|
| `Papi::V3::OrdersController#payment_methods` | `redirect_3ds_mode` в ответе |
| `Papi::V3::CertificatesController#payment_methods` | `redirect_3ds_mode` в ответе |
| `Papi::V3::PaymentStatusMethods#payment_methods_action` (`GET /payments/payment_methods`) | `redirect_3ds_mode: Settings.redirect_3ds_mode? && !app_request?` |
| `papi/v3/orders/prebuild.json.jpbuilder` | `redirect_3ds_mode` в ответе prebuild |
| `PaymentController#redirect_3ds` | `separate_tab = Settings.redirect_3ds_mode? && !payment.from_app?` — собственно ветвление: рендер страницы с iframe либо `redirect_to /transaction` |

Глобальный флаг уже включён для одних партнёров и мешает другим: включение меняет поведение всех сразу. Обратная ситуация — партнёр, которому отдельная вкладка нужна, не может её получить, пока флаг выключен глобально.

## Scenarios

1. **Партнёр «По общей настройке», флаг выключен.** `separate_tab_3ds?` → `false`. `payment_methods` и `prebuild` отдают `redirect_3ds_mode: false`; `PaymentController#redirect_3ds` рендерит страницу с iframe. Поведение полностью совпадает с текущим (значение колонки по умолчанию).
2. **Партнёр «По общей настройке», флаг включён.** `separate_tab_3ds?` → `true`. Все места отдают `true`, `PaymentController` редиректит на `/transaction`. Текущее поведение сохранено.
3. **Партнёр «Во фрейме», флаг включён глобально.** `separate_tab_3ds?` → `false`, несмотря на включённый глобальный флаг: iframe-флоу, `redirect_3ds_mode: false` во всех ответах. Остальные партнёры продолжают работать по глобальной настройке.
4. **Партнёр «В новой вкладке», флаг выключен глобально.** `separate_tab_3ds?` → `true`: отдельная вкладка только у этого партнёра, остальные остаются на iframe.
5. **Партнёр «В новой вкладке», платёж из приложения LT.** `payment.from_app?` безусловно перебивает выбор партнёра: `PaymentController` рендерит iframe-страницу, `MD` не сохраняется. В PAPI `payment_methods_action` отдаёт `false`, потому что там уже есть `!app_request?`.
6. **Партнёр «В новой вкладке», запрос из приложения LT к остальным ручкам.** `orders#payment_methods`, `orders#prebuild`, `certificates#payment_methods` тоже должны отдавать `false` для `app_request?`, иначе клиент приложения получает `true` из prebuild и `false` из `/payments/payment_methods` для одного и того же платежа.
7. **Сертификатный заказ.** Режим определяется партнёром заказа (`payment.order.partner`) и на ручке `certificates#payment_methods` — партнёром запроса.
8. **Смена настройки в админке.** В карточке партнёра выбирается один из трёх вариантов, значение сохраняется; изменение попадает в `paper_trail`. Значение вне списка не сохраняется.
9. **Партнёр не найден у заказа.** `payment.order.partner` пуст (не должно случаться: `orders.partner_id` — обязательная связь). Предикат вызывается на партнёре, `nil` не допускается; если такое случится, это ошибка данных, а не повод молча менять поведение.

## Current system state

- `Settings.redirect_3ds_mode?` — `REDIS.static.with { |c| c.get('settings:redirect_3ds_mode') == '1' }`; чекбокс в `app/views/admin/settings/_form.html.haml:24`, атрибут в `Settings::ATTRIBUTES`.
- `PaymentController#redirect_3ds` — `separate_tab = Settings.redirect_3ds_mode? && !payment.from_app?`; при `separate_tab` сохраняется `MD`, затем `redirect_to(redirect_3ds_target(payment), status: :see_other)`, иначе `render(:redirect_3ds)` (страница кладёт `window.LT_Payment3dsData`, который читает `Payment3dsPopup`/`PaymentHidden3dsPopup`).
- `Payment#from_app?` — `data[:from_app].present? || mobile_app?`; платежи создаются с `from_app: app_request?` в `Papi::V3::PaymentsConcern#build_payment`.
- `Papi::PartnerAccess#app_request?` — `@app_partner&.id == ::Partner::LT_APP_ID`; `@app_partner` выставляется до подмены `@partner` на WL-партнёра, поэтому признак сохраняется и в WL-режиме приложения.
- `Partner` — `ADMIN_PERMITTED_ATTRIBUTES` (whitelist админ-формы), `has_paper_trail`, enum-атрибуты в стиле `promo_code_provider` (строковые значения, `prefix: true`).
- Клиент читает `redirect3DSMode` из ответов `prebuild`, `payment_methods` и `/payments/payment_methods` и передаёт его в `Payment3dsPopup` / `PaymentHidden3dsPopup`; при `true` форма 3DS submit'ится в новую вкладку, при `false` — в iframe.

## Implementation decisions

### Колонка и enum

- Миграция: `add_column :partners, :redirect_3ds_mode, :string, default: 'global', null: false`. `db/schema.rb` откатывается через `git checkout` и дописывается вручную: колонка в `create_table "partners"` (рядом с `promo_code_provider`) и строка `version`.
- `Partner`: `enum :redirect_3ds_mode, { global: 'global', iframe: 'iframe', separate_tab: 'separate_tab' }, prefix: true`. Префикс даёт `redirect_3ds_mode_global?` / `redirect_3ds_mode_iframe?` / `redirect_3ds_mode_separate_tab?` и не конфликтует с `separate_tab_3ds?`.
- Значение по умолчанию на уровне БД и `null: false` — старые партнёры получают `global` без бэкфилла.
- Атрибут добавляется в `ADMIN_PERMITTED_ATTRIBUTES`.

### Предикат

```ruby
def separate_tab_3ds?
  return Settings.redirect_3ds_mode? if redirect_3ds_mode_global?
  redirect_3ds_mode_separate_tab?
end
```

- Единственная точка правды для «партнёр + глобальная настройка». Call sites не знают про `Settings`.
- Метод кладётся в публичную доменную часть `Partner` рядом с `lt?` / `new_widgets_api?`.

### Запрет для мобильного приложения

- `PaymentController#redirect_3ds`: `separate_tab = payment.order.partner.separate_tab_3ds? && !payment.from_app?` — исключение для приложения сохраняется безусловным (согласовано в задаче: приложение не умеет открывать отдельную вкладку).
- `PaymentStatusMethods#payment_methods_action` сохраняет `&& !app_request?`.
- `orders#payment_methods`, `prebuild`, `certificates#payment_methods` **получают** такое же `&& !app_request?`: сейчас они его не применяют, и с per-partner настройкой это стало бы реальным рассинхроном (партнёр «В новой вкладке» + приложение LT → `prebuild` говорит `true`, `/payments/payment_methods` говорит `false`). Поведение для приложения меняется на «всегда iframe», что и так обеспечивает `PaymentController#redirect_3ds`.

### Партнёр в местах вызова

- `orders#payment_methods`, `prebuild`, `payment_methods_action` (`/payments/payment_methods`) — **партнёр заказа** (`@order.partner`), а не `@partner` аутентификации: `Order::AssignPartnerData` может переставить партнёра заказа (WL, aflt-метка, прошлый заказ), а `PaymentController#redirect_3ds` ветвится именно по `payment.order.partner`. Иначе клиент и сервер разошлись бы на одном платеже.
- `PaymentController#redirect_3ds` — `payment.order.partner`.
- `certificates#payment_methods` — общая настройка `Settings.redirect_3ds_mode?`: сертификатный заказ создаётся `CertificateCreator` без `partner_id`, поэтому `PaymentController` для него тоже берёт общую настройку.
- `Partner.separate_tab_3ds?(partner)` — единый резолвер: режим партнёра, а при `nil` партнёре (сертификатные заказы) общая настройка.

### Админка

- `app/views/admin/partners/_form.html.haml`: селект в секции «Настройки» рядом с платежными настройками, `include_blank: false`, коллекция из `Partner.redirect_3ds_modes.keys` с переводами.
- `app/admin/partners.rb`: `row(:redirect_3ds_mode)` в show-блоке и в `ADMIN_PERMITTED_ATTRIBUTES`.
- I18n: `activerecord.attributes.partner.redirect_3ds_mode` и блок `partner/redirect_3ds_mode` (`global: По общей настройке`, `iframe: Во фрейме`, `separate_tab: В новой вкладке`) в `config/locales/ru.yml` — по образцу `partner/promo_code_provider`.

### Документация PAPI

- Контракт меняется: `redirect_3ds_mode` больше не «глобальная настройка», а настройка партнёра; в описании это отражается.
- Новые файлы exact version по `docs/papi/v3/README.md` (операция описывается целиком, не патчем): `payments/3.16.yml`, `orders/3.17.yml`, `certificates/3.1.yml`.
- Проверка: `ruby script/api_docs.rb compile-controller payments 3.16` и т.д.

## Testing decisions

- **Хороший тест** проверяет внешнее поведение: `separate_tab_3ds?` на модели, поле `redirect_3ds_mode` в ответе ручки, редирект vs рендер страницы в `PaymentController`. Не проверяет внутренние вызовы.
- `spec/models/partner_spec.rb`: `#separate_tab_3ds?` — таблица «значение партнёра × глобальный флаг» (сценарии 1–4), без заглушек `Settings` где возможно (стаб `Settings.redirect_3ds_mode?` для ветки `global`).
- `spec/controllers/papi/v3/payments_controller_spec.rb` (`#payment_methods`): существующие стабы `Settings` заменяются на значения enum партнёра; сохраняются сценарии «приложение» и «WL-режим приложения»; добавляется «партнёр `iframe` при включённом глобальном флаге» (сценарий 3).
- `spec/controllers/papi/v3/certificates_controller_spec.rb` (`#payment_methods`): то же.
- `spec/controllers/papi/v3/orders_controller/*`: prebuild/`payment_methods` отдают режим партнёра и `false` для `app_request?` (сценарий 6).
- `spec/controllers/payment_controller_spec.rb` (`#redirect_3ds`): рендер iframe-страницы для партнёра `iframe` при включённом глобальном флаге; редирект на `/transaction` для партнёра `separate_tab` при выключенном флаге; сохранение/несохранение `MD`; приложение — всегда iframe (сценарии 3–5).
- `spec/admin/partners_spec.rb`: в форме есть `partner[redirect_3ds_mode]`; сохранение значения через `PATCH /admin/partners/:id` меняет колонку.
- **Регрессия**: существующие спеки `payment_controller_spec.rb`, `payments_controller_spec.rb`, `certificates_controller_spec.rb`, `orders_controller/**`, `spec/models/partner_spec.rb`.

## Out of scope

- Настройка режима 3DS на уровне заказа, платёжной системы или банка.
- Изменение клиентского кода (`client/lt-modules`): контракт `redirect_3ds_mode` не меняется, меняется только источник значения на бэкенде.
- Удаление глобальной настройки `Settings.redirect_3ds_mode`.
- Обучение приложения LT отдельной вкладке.
- Автоматический подбор режима (например, по банку-эквайеру).

## Further notes

- Хотфикс: paired PR, ветки `hotfix/<slug>` в `master` и `hotfix/<slug>-dev` в `develop`, второй — cherry-pick первого коммита.
- Миграция безопасна для rolling deploy: колонка с дефолтом и `null: false` добавляется одной операцией; код, читающий `redirect_3ds_mode` только после деплоя, до применения миграции даст исключение, поэтому порядок — сначала миграция, затем деплой (стандартный для проекта).
- Риск: рассинхрон клиента и `PaymentController` при неверном выборе партнёра. Митигация — единственный предикат и явное `payment.order.partner`.
- Глобальный флаг остаётся включённым или выключенным как есть; партнёрам, которым нужен другой режим, выставляется значение в карточке.
