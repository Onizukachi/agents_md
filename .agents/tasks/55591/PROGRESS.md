# LT-55591 Progress

## 2026-11-10 — реализация

Ветка `feature/LT-55591-subagent-order-extra-notifications` от свежего `develop` (`84432be52`). Не закоммичено.

### Что сделано

- `Order::ExternalNotification::Delivery` (новый): фильтр получателя `deliverable?(order)` и доставка `call(order, messages)`. Создаёт `ExternalNotification` на каждое сообщение и ставит `OrderExternalNotification` (на staging — синхронно).
- `Order::ExternalNotification::Sender` переведён на `Delivery`. Логика белого списка, отсечки `package_update` и `info`, документы при `documents_sent` не менялись. Убраны `attr_reader :partner`, `partner_notificable?` и `notify_webhook_url`: они переехали в `Delivery`. Ссылку на `partner_notificable?` в комментарии `Order::TariffPrepaymentNotifier` обновил.
- `OrderExtras::SubagentNotifier` (новый, `ApplicationService`): собирает сообщение `order_id, event, event_timestamp, event_reference (SecureRandom.uuid), changes [before, after], message, action_code`, подавляет «Кино» по `name` в любом из срезов, отправляет через `Delivery`.
- `OrderExtra`:
  - `SUBAGENT_VISIBLE_ATTRIBUTES` / `SUBAGENT_EDITABLE_ATTRIBUTES`;
  - первый `after_create` выключает уведомления до коммита или отката транзакции создания;
  - `after_update` определяет cancel, restore или update;
  - `after_destroy` (только для активной услуги) шлёт cancel;
  - срезы считаются в момент сохранения, доставка идёт через `current_transaction.after_commit`.
- `Requester`: сортировка `created_at, id`.
- I18n: `order_extra.subagent_notifier.{update,cancel,restore}` в `config/locales/ru.yml`.

### Тесты

- `spec/models/order_extra_spec.rb`, `describe 'subagent notifications'`: 12 примеров (сценарии 1–11, 14 и порядок событий из сценария 8).
- `spec/services/order_extras/subagent_notifier_spec.rb`: 11 примеров (формат, reference, постановка доставки, «Кино» до/после, не субагент, нет вебхука для клиента, development).
- Мутационная проверка: если отключить выключение уведомлений на создании, падает пример `when the extra changes in the transaction that created it`.
- Регрессия зелёная:
  - sender, serializer, external_notification, tariff_prepayment_notifier, order_log, attachment — 137 примеров вместе с новыми;
  - tourist, papi/v3 order_extras, client_tourists, manager order_extras, update_price_service, supplier_extra/booker, order_extras, supplier_extra — 203 примера.
- `spec/models/order_spec.rb spec/models/concerns`: 1 падение `order_spec.rb:1345` (`write_to_abandoned_carts_cache?`). При отдельном запуске оно зелёное (3 из 3), падает только в общем прогоне файла. С допуслугами не связано.

## Rejected / changed

- **Интерфейс сервиса: `action:` вместо `event:`.** `call(order_extra:, action:, before:, after:)`, где `action` — `:update`, `:cancel` или `:restore`. Восстановление и создание дают одно событие `order_extra_create`, но разный текст `message`. По `event` их не различить, по `action` — да.
- **Тексты `message` — ключи I18n**, а не строки в коде (правило конвенций). Сами тексты те же, что в спеке.
- **Ошибка доставки после коммита ловится и уходит в Sentry**, а не пробрасывается. Данные к этому моменту уже закоммичены. Проброс превратил бы, например, правку в менеджерке в 500 при сохранённой услуге. В спеке этого не было.
- **Сценарий 16 (тот же `event_reference` при переотправке) отдельным тестом не покрыт.** Гарантию даёт существующий `Requester#create_unsend_notification`: он копирует `request` целиком, и мы его не меняли. Тест проверяет только, что reference — UUID и лежит в `request`.
- **Сценарий 17 (порядок при одинаковой секунде)** покрыт порядком записей в модельном спеке. Отдельного спека `Requester` в репозитории нет, сортировку `created_at, id` отдельно не тестировал.

## 2026-11-10 — убрано выключение уведомлений на создании

Поиск по коду: в транзакции создания допуслуги её видимые поля нигде не меняются.
- Повторно сохраняет запись только `assign_split_value!`, и он пишет `is_split` — поле вне среза.
- Бронирование из `after_create` (`FinalBook`, `Order::TransferCorrection`) пишет только `supplier_extra`.
- `Builder`, `AttachUpsaleOption` и покупка в CRM сохраняют новую запись один раз.
- Единственный теоретический случай — мгновенный `cancelled` от Booker в `ApplyResponse`. Он вызывает `cancel!` на другом экземпляре, и флаг на объекте его всё равно не закрывал.

По решению пользователя `mute_subagent_notifications_until_commit` и `subagent_notifications_muted?` удалены. Требование «доводки при создании событий не дают» обеспечивает фильтр по видимым полям.

Тест `when the extra changes in the transaction that created it` заменён на `when a split extra is created / sends nothing on assigning its split value` (`code_name: 'infant'` → `assign_split_value!` → `update!(is_split: true)`). Мутация: если добавить `is_split` в `SUBAGENT_EDITABLE_ATTRIBUTES`, тест падает.

Прогон: notifier, order_extra, sender, serializer, external_notification, tariff_prepayment_notifier, order_log, attachment, tourist, manager order_extras, supplier_extra/booker, order_extras — 249 примеров, 0 падений.

## Rejected / changed

- **Нет выключения уведомлений в транзакции создания** (в спеке: «флаг ставится в `after_create` и снимается после коммита или отката»). Изменения видимых полей в транзакции создания, если такие появятся, уходят субагенту как `order_extra_update`. Неизвестный `id` субагент обязан принимать (Q9).
