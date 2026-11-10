# LT-55591 Уведомлять субагентов о добавлении, изменении и удалении допуслуг в заказе

## Summary

Субагент получает вебхук `order_extra_create`, когда в заказ добавляют Order Extra, но не узнаёт, что услугу изменили или отменили. Его система расходится с нашей по составу и стоимости заказа.

Добавляем два события: `order_extra_update` (`changes = [до, после]`) и `order_extra_cancel` (`changes = [до, null]`). Восстановление отменённой услуги шлёт уже существующий `order_extra_create` (`[null, после]`).

Ключевые решения:

- События порождает **сама модель `OrderExtra`** (коллбэки на изменение и удаление), а не менеджерские контроллеры. Поэтому они ловят и автоматические пути: визу из `Tourist`, отмену по ответу Booker, замену пакета.
- События идут **напрямую в `ExternalNotification`, без `OrderLog`**: без разбора текста сообщения, без антиспама логов и без лишних синхронизаций Альфа-миль. Отправку из `Sender` выносим в общий модуль, и его вызывают оба пути.
- **`order_extra_create` не трогаем**: формат, момент отправки и путь через `OrderLog` остаются как есть.
- В `changes` лежит тот же срез услуги, что уже отдаёт create: `id, name, price, free, order_id, code_name, dynamic, additional_price`. Правки других полей (`markup`, `is_split` и т.п.) событий не дают.
- Отправка выполняется **только после коммита** транзакции, в которой изменилась услуга. При откате ничего не уходит.
- Обычная фича от `develop`, не хотфикс.

## Problem

Субагент продаёт наши Заказы своим клиентам и ведёт их у себя по нашим вебхукам. Состав Order Extra в Заказе меняется после создания: менеджер правит цену или название, отменяет и восстанавливает услугу, поставщик отменяет трансфер, турист меняет визовый сервис, при замене пакета исчезают бесплатные услуги. Ни одно из этих изменений до субагента не доходит. Он показывает клиенту устаревший состав и цену, и сверка с нами расходится.

## Solution

Каждое изменение активной Order Extra, видимое субагенту, превращается в вебхук с полным снимком услуги до и после:

| Действие | Событие | `changes` |
|---|---|---|
| Изменили у активной услуги поле из видимого среза | `order_extra_update` | `[срез до, срез после]` |
| Отменили активную услугу (`cancel`) или удалили её запись | `order_extra_cancel` | `[срез до, null]` |
| Восстановили отменённую услугу (`restore`) | `order_extra_create` | `[null, срез после]` |
| Добавили услугу | `order_extra_create` | без изменений, действующий путь |

Получатели и фильтры те же, что у действующего `order_extra_create`. Субагент различает услуги по `id`.

## Current system state

**Отправка вебхуков субагенту**

- `OrderLog` после создания вызывает `make_notify` (`app/models/order_log.rb:74`, `:117`) → `Order::ExternalNotification::Sender#send` (`app/services/order/external_notification/sender.rb:14`).
- В `Sender` первые строки — фильтр получателя: заказ с партнёром, `partner_notificable?` (`is_outer_first_line || subagent_wl?`, `:51`; `subagent_wl?` — это `is_wl_hooks`, `app/models/partner.rb:576`), есть `partner.notify_webhook_url_for(order)`, окружение не `development` (`:17`).
- Белый список событий: `permitted_event?` (`sender.rb:59`). Из событий допуслуг в нём только `order_extra_create`. `unpermitted_event?` (`:65`) подавляет `order_extra_create`, если в сообщении есть «Кино».
- Отправка: `::ExternalNotification.create(url:, partner_id:, order_id:, request: message.to_json, event:)`, затем `OrderExternalNotification.perform_in(15.seconds, order.id)`. На staging вместо этого `sleep(0.5)` и синхронный `perform` (`sender.rb:23–36`).
- `Order::ExternalNotification::Requester` отправляет все недоставленные уведомления заказа по `created_at ASC` (`requester.rb:12`). При ошибке дублирует запись целиком, вместе с `request` (`create_unsend_notification`, `:67`). Колонка `external_notifications.created_at` — `datetime` без дробных секунд.

**Формат `order_extra_create`**

- Серализатор `Order::ExternalNotificationSerializer` отдаёт `order_id, event, event_timestamp, event_reference, changes, message, action_code` (`app/services/order/external_notification_serializer.rb:35–43`). `event_reference` — uuid_v5 от `order_log.id`.
- `extra_data` (`:122`) выделяет имя услуги из текста сообщения и ищет услугу по имени (`find_by(name:)`): `changes = [nil, extra.slice(:id, :name, :price, :free, :order_id, :code_name, :dynamic, :additional_price)]`. Это массив, а не хэш по полям.
- Логи `order_extra_create` пишут: `OrderCreation#logged_order_extras` при создании заказа (`app/models/concerns/order_creation.rb:261`), `OrdersController#create_insurance_log` (`app/controllers/orders_controller.rb:455`) и `ManagerTracker` при ручном добавлении в менеджерке (`app/controllers/manager/orders_controller.rb:314`, `:350`).

**`OrderExtra`**

- Состояние: `state` (`created` — активна, `canceled` — отменена), AASM-события `cancel` и `restore`. У `restore` есть гард `can_restore?` (`app/models/order_extra.rb:112–128`). `scope :active` (`:81`).
- `has_paper_trail` на update/destroy (`:131`).
- Сразу после создания `assign_split_value!` делает `update!(is_split:)` (`:60`, `:258`). `markup` считается в `before_create`.
- Колонки: `name, price (int), free (bool), code_name, dynamic (bool), additional_price (int), scope, extra_template_id, supplier_extra_id, mandatory, state, is_split, markup, upsale_option_key`.
- `Order#update_extras_markup` меняет `markup` через `update_all`, в обход коллбэков (`app/models/order.rb:4124`).

**Где допуслуги меняются, отменяются и удаляются**

| Путь | Что делает | Пишет `OrderLog` |
|---|---|---|
| Менеджерка: `Manager::ResourceController#update` (`app/controllers/manager/resource_controller.rb:25`) | правка `name, price, free, is_split, state, markup` | да, `order_extra_update` через `ManagerTracker` |
| Менеджерка: `Manager::OrderExtrasController#destroy` / `#restore` | `cancel!` (или отмена трансфера Booker) / `restore!` | да, `order_extra_cancel` / `order_extra_restore` |
| `Tourist#try_update_visa_extras!` (`app/models/tourist.rb:235`, вызов из `after_update`, `:196`) | `cancel!`, `restore!`, затем `update!(name:, price:)` в транзакции туриста | нет |
| `Tourist#try_create_visa_extras!` (`tourist.rb:218`) | `OrderExtra.create!` | нет, и `order_extra_create` тоже не уходит |
| `SupplierExtra::Booker::ApplyResponse` (`app/services/supplier_extra/booker/apply_response.rb:45`) | `cancel!` по ответу поставщика | нет |
| `Extras#delete_old_extras!` (`app/models/concerns/extras.rb:308–315`), при замене пакета | физически удаляет нулевые услуги, которых нет в новом пакете | нет |

- `ManagerTracker` пишет для `OrderExtra` коды `order_extra_<action>` (`app/base/manager_tracker.rb:168`). В `data` для `update` лежит `{поле => [было, стало]}` по всем изменённым полям, для остальных действий — все атрибуты (`:49`). Партнёру эти логи не уходят: их нет в белом списке `Sender`.
- `PartnerBonuses::AlfaMiles::ContentUpdateWorker` слушает коды `order_extra_create/update/cancel/restore` (`app/workers/partner_bonuses/alfa_miles/content_update_worker.rb:14`). Он срабатывает от `OrderLog#sync_with_alfa_miles`.
- `OrderLog#similiar_message_spam` отклоняет лог с тем же сообщением и `data` в течение часа, если `action_code` не в `SPAM_CHECK_FREE_ACTION_CODES` (`order_log.rb:20`, `:151`).

**Окружение**

- Rails 8.1.3: доступен `ActiveRecord::Base.current_transaction.after_commit`. Вне транзакции он выполняет блок сразу, при откате блок отбрасывается. В `app/` этот API пока не используется.
- В спеках `use_transactional_fixtures = false`, `after_commit` срабатывает обычным образом.
- Документации по вебхукам субагентов в репозитории нет.

## Scenarios

1. Менеджер меняет цену активной услуги. Уходит `order_extra_update`: в `changes` два среза, отличаются `price`.
2. Меняются `name`, `free`, `additional_price`, `code_name` или `dynamic` активной услуги. Уходит `order_extra_update`. Если за одно сохранение изменилось несколько видимых полей, событие одно.
3. Меняются только внутренние поля (`markup`, `is_split`, `supplier_extra_id`, `mandatory`, `scope`, `extra_template_id`, `upsale_option_key`, `updated_at`). Событий нет.
4. `update_extras_markup` меняет `markup` через `update_all`. Событий нет.
5. Активную услугу отменяют через `cancel!` (менеджерка, ответ Booker, турист выбрал `no_visa`). Уходит `order_extra_cancel` с `[срез до отмены, null]`.
6. Меняют поля уже отменённой услуги. Событий нет.
7. Отменённую услугу восстанавливают через `restore!`. Уходит `order_extra_create` с `[null, срез после восстановления]` и тем же `id`.
8. Турист меняет визовый сервис обратно на визу. В одной транзакции услуга восстанавливается, потом у неё меняются название и цена. Уходят два события в таком порядке: `order_extra_create` (срез сразу после `restore!`), затем `order_extra_update` (до — тот же срез, после — с новыми названием и ценой).
9. При замене пакета `delete_old_extras!` удаляет активную нулевую услугу. Уходит `order_extra_cancel` со срезом удалённой записи. Удаление записи, которая уже была отменена, событий не даёт.
10. Создаётся новая услуга, и в той же транзакции её обновляют (`assign_split_value!` и прочие доводки при создании). Новый механизм событий не шлёт. `order_extra_create`, если он положен, уходит действующим путём через `OrderLog`.
11. Транзакция, в которой изменили услугу, откатывается. Событий нет.
12. Партнёр заказа не субагент: не `is_outer_first_line`, не `is_wl_hooks`, или у него нет вебхук-URL для этого заказа, или у заказа нет партнёра. Событий нет.
13. Название услуги до или после изменения содержит «Кино». Событий нет.
14. В заказе две услуги с одинаковым названием, меняют одну из них. Событие несёт `id` именно изменённой услуги, вторая не затронута.
15. Менеджер правит услугу в менеджерке. Партнёру уходит ровно одно событие (из модели). Менеджерский `OrderLog` с `order_extra_update` / `order_extra_cancel` пишется как раньше и партнёру не отправляется.
16. Субагент не ответил 2xx, и уведомление переотправляется. Повторная доставка несёт тот же `event_reference`.
17. Несколько событий по одному заказу созданы в одну и ту же секунду (сценарий 8). Субагенту они уходят в порядке создания.
18. Услуга изменилась в окружении `development`. Событий нет, как и у остальных вебхуков.

## Implementation decisions

**Порождение событий в модели**

- `OrderExtra` определяет событие в `after_update` по сохранённым изменениям:
  - `state`: `created → canceled` — `order_extra_cancel`, `before` = срез со значениями до сохранения, `after = nil`;
  - `state`: `canceled → created` — `order_extra_create`, `before = nil`, `after` = текущий срез;
  - `state` не менялся, услуга активна, изменилось хотя бы одно поле среза кроме `id` и `order_id` — `order_extra_update`, `before` = срез до сохранения, `after` = текущий срез;
  - во всех остальных случаях событий нет.
- `after_destroy`: если услуга была активна, порождается `order_extra_cancel` с её срезом.
- Если запись создана в той же транзакции, `after_update` событий не порождает. Флаг ставится в `after_create` и снимается после коммита или отката.
- Срез события вычисляется **в момент сохранения**, и в событии остаются значения на тот момент. Доставка откладывается до коммита внешней транзакции через `ActiveRecord::Base.current_transaction.after_commit`. Если транзакции нет, блок выполняется сразу. Так несколько сохранений одной записи в транзакции дают несколько событий в правильном порядке и не зависят от того, на каком экземпляре Rails вызовет `after_commit`. При откате события пропадают.
- Срез услуги — единый метод с полями `id, name, price, free, order_id, code_name, dynamic, additional_price`. Тот же набор использует серализатор create, но его путь в этой задаче не меняется.

**Сервис события для субагента** (`OrderExtras::SubagentNotifier`, интерфейс `call(order_extra:, event:, before:, after:)`)

- Решает, кому отправлять: тот же фильтр получателя, что у `Sender` (см. ниже). Плюс подавление «Кино»: если `name` в `before` или `after` содержит «Кино», событие не отправляется.
- Собирает сообщение в форме действующих вебхуков:

  ```json
  {
    "order_id": 84324759,
    "event": "order_extra_update",
    "event_timestamp": 1762770000,
    "event_reference": "<uuid>",
    "changes": [{ "id": 1, "name": "…", "price": 1000, "free": false, "order_id": 84324759, "code_name": "…", "dynamic": false, "additional_price": null },
                { "id": 1, "name": "…", "price": 1500, "free": false, "order_id": 84324759, "code_name": "…", "dynamic": false, "additional_price": null }],
    "message": "Изменена доп. услуга \"…\"",
    "action_code": "order_extra_update"
  }
  ```

  - `action_code` совпадает с `event`, как в действующем `order_extra_create`.
  - `message` — человекочитаемый текст: `Изменена доп. услуга "<name>"`, `Отменена доп. услуга "<name>"`, `Восстановлена доп. услуга "<name>"`.
  - `event_reference` — `SecureRandom.uuid`, генерируется один раз при сборке и сохраняется в `request`. При переотправке `Requester` копирует `request` целиком, поэтому reference стабилен и годится для дедупликации у субагента. От обсуждавшегося uuid_v5 от `id` записи отказались: он требовал бы двух записей в БД и не даёт дополнительной гарантии.
  - `event_timestamp` — время сборки события (Unix-секунды).
- Передаёт сообщение в общий модуль доставки.

**Общий модуль доставки** (выносится из `Sender`)

- Отвечает за две вещи:
  - фильтр получателя по заказу: есть партнёр, `is_outer_first_line || subagent_wl?`, есть `notify_webhook_url_for(order)`, окружение не `development`;
  - доставку одного или нескольких сообщений: `ExternalNotification.create(url:, partner_id:, order_id:, request:, event:)` на каждое сообщение, затем `OrderExternalNotification.perform_in(15.seconds, order.id)` (на staging — `sleep(0.5)` и синхронный `perform`, как сейчас).
- `Sender` использует этот модуль. Его собственная логика (`permitted_kind?`, `permitted_event?`, `unpermitted_event?`, отсечка `package_update` с нулевой ценой, документы при `documents_sent`) не меняется. Белый список `Sender` **не расширяется**: менеджерские `order_extra_update`, `order_extra_cancel` и `order_extra_restore` по-прежнему партнёру не уходят.

**Порядок доставки**

- `Requester` сортирует недоставленные уведомления по `created_at, id` вместо одного `created_at`. При одинаковой секунде события уходят в порядке создания (сценарий 17).

**Без изменений схемы**: новые таблицы и колонки не нужны.

## Testing decisions

Хороший тест проверяет внешнее поведение: какое уведомление ушло субагенту после реального изменения допуслуги (`ExternalNotification` в БД, разобранный `request`, поставленная задача `OrderExternalNotification`). Внутренние флаги и порядок вызова коллбэков не проверяем.

**Спек `OrderExtra`** (`spec/models/order_extra_spec.rb`, новый `describe` про уведомления субагенту) — основной. На реальных записях: заказ партнёра с фабрикой `:hooks`, услуга из фабрики `:order_extra`. Покрывает сценарии 1–11, 14 и 17. Для каждого действия с услугой проверяем, сколько `ExternalNotification` появилось, их `event` и `changes`. Для сценария 8 восстановление и изменение делаем внутри одной транзакции. Для сценария 11 — откат транзакции.

**Спек `OrderExtras::SubagentNotifier`** — формат и фильтры, сценарии 12, 13, 16 и 18:
- форма сообщения: ключи, `action_code`, `message`, `changes`;
- `event_reference` — UUID, сохранён в `request`;
- партнёр не субагент, нет вебхук-URL, нет партнёра — уведомления нет;
- «Кино» в `before` или `after` — уведомления нет;
- поставлен `OrderExternalNotification.perform_in`.

**Регрессия без изменений в спеках**: `spec/services/order/external_notification/sender_spec.rb`, `spec/services/order/external_notification_serializer_spec.rb` (контекст `with order_extra changes`), `spec/services/order/external_notification_spec.rb`, `spec/models/order_log_spec.rb`. Если для порядка (`created_at, id`) есть спек `Requester`, прогнать и его.

Образцы: `sender_spec.rb` (стабы `ExternalNotification.create` / `OrderExternalNotification.perform_in`), фабрика `partner :hooks` (`spec/factories/partner.rb:53`), трейты `order_extra` (`spec/factories/order_extra*.rb`). Описания `describe`, `context` и `it` на английском, по `rspec-style-guide`.

Админку и rake спеками не покрываем.

## Out of scope

- Изменение пути, момента и формата `order_extra_create` при добавлении услуги. Поиск услуги в `extra_data` по имени, а не по `id`, остаётся как есть.
- Отправка `order_extra_create` для услуг, которые создаются без `OrderLog`: виза из `Tourist#try_create_visa_extras!`, `lock_flight` из Турвизора, страховка из `InsuranceRecreator`. Для таких услуг субагент может получить `order_extra_update` или `order_extra_cancel` по `id`, о котором раньше не слышал.
- Изменения в менеджерских `OrderLog`, `ManagerTracker`, антиспаме `OrderLog` и синхронизации Альфа-миль.
- Удаление заказов: заказы не удаляются.
- Изменения, сделанные в обход коллбэков (`update_all`, `update_columns`, SQL).
- Публичная документация вебхуков: в репозитории её нет.

## Further notes

- **Контракт для субагентов.** В описании PR перечислить новые события и правила:
  - `order_extra_update` и `order_extra_cancel` могут прийти по `id`, для которого не было `order_extra_create`. Субагент делает upsert или игнорирует;
  - восстановление приходит как `order_extra_create` с уже известным `id`;
  - дедупликация по `event_reference`.
  Кого из субагентов и как предупредить до выкатки, решает автор задачи.
- **Без двойной отправки.** Менеджерское действие порождает и `OrderLog` (через `ManagerTracker`), и событие модели. Партнёру уходит только событие модели, потому что белый список `Sender` не расширяется. Если кто-то позже добавит `order_extra_update` или `order_extra_cancel` в белый список, появятся дубли.
- **`changes` у create — массив, а не хэш по полям**, в отличие от `tourist_update` и `flights`. Новые события повторяют форму create.
- Сценарий 8 (виза: восстановление и правка в одной транзакции туриста) — единственный известный путь, где за одну транзакцию с услугой происходит несколько изменений. Он и задаёт требование доставлять после коммита с сохранением порядка.
