# LT-55638 Progress

## 13.11.2026 — реализация по новой спеке (ветка `feature/LT-55638-operator-appeals`)

### Сделано

- Миграция `20261113110614_create_order_appeals` (таблица `order_appeals`: `order_id`, `manager_id`, `kind`, `status`, `token` с уникальным индексом, `data` JSON, `file`, `submitted_at`, `attachment_id`), миграция применена в dev, тестовая БД пересоздана, `db/schema.rb` правился вручную в старом формате.
- Модель `OrderAppeal` (виды `request`/`minimization`/`claim`, статусы `created`/`submitted`, сроки формы 30 и скачивания 180 дней, `attach_to_order!`), `OrderAppealUploader` (закрытое хранилище по образцу клиентских документов), `Order has_many :order_appeals`.
- `OrderAppeals::Prefill` (данные заказа), `OrderAppeals::Submit` (валидация, фиксация данных, PDF, статус под блокировкой строки, повторная отправка идемпотентна).
- `OrderAppealPdf` + макет `app/views/order_appeals/letter.pdf.haml`: два режима — PDF и превью для менеджера (серые подсказки вместо текста).
- Публичный `OrderAppealsController` (`/appeals/:token`, `POST`, `/pdf`), макет `order_appeal` и три экрана (форма, «отправлено», «срок истёк»), `noindex`, `no-store`.
- Менеджерская часть: `Manager::OrderAppealsController` (`create` возвращает ссылку, `preview` отдаёт HTML), Ember-модель `order_appeal`, правки окна шаблонов (блок «Так будет выглядеть обращение», создание обращения при «Вставить шаблон»).
- Админка «Заказы → Обращения к туроператору» (список, фильтры, «Скачать PDF», «Прикрепить к заказу»).
- Одноразовая rake-задача `operator_appeals:create_templates` (категория и три шаблона, идемпотентная; в dev запущена дважды).
- Тексты видов (заголовки, подсказки, названия файлов), статусы и страницы — в `config/locales/ru.yml` (`order_appeals.*`, `activerecord.*.order_appeal`).
- Спеки: `spec/services/order_appeals/prefill_spec.rb`, `spec/services/order_appeals/submit_spec.rb`, `spec/models/order_appeal_spec.rb`, `spec/pdfs/order_appeal_pdf_spec.rb`, фабрика `:order_appeal`; все зелёные вместе с соседними (`spec/routing`, `spec/controllers/manager`, `orders_controller`, `order_statement`, `order_price_pdf`).

### Rejected / changed

- Публичная и менеджерская части проверены вручную через временные спеки и интеграционную сессию (форма, ошибки, PDF-ответ, повторное открытие, 404, `create` и `preview` менеджера, список/скачивание/прикрепление в админке); временные спеки удалены, постоянных спеков на контроллеры и админку нет (решение 13.11).
- Маршрут превью менеджера: `GET /order_appeals/preview` лежит в `manager`-пространстве вне блока `defaults format: :json` (иначе `render_ember` отдавал бы страницу Ember); `create` — в `manager_controller_actions.rb` рядом с `client_one_time_auth_tokens`.
- Добавлен метод `Order#public_domain` (домен публичных страниц с учётом WL); существующие `public_url` и `transaction_url` не трогал, они дублируют ту же логику.
- `enum :kind` с `validate: true`: неизвестный вид даёт ошибку валидации (422 из менеджерского `create`), а не исключение.
- Метка у клиентской формы: `form_with` в проекте не генерирует `id`, поэтому `id` и `for` заданы явно.
- Локально Spring отдаёт устаревшее состояние после правок маршрутов и файлов: для `rails runner`/`rake` использовать `DISABLE_SPRING=1`.
- Подсказка «К претензии/минимизации прилагаю: 1. 2. 3.» лежит внутри placeholder текстового поля (в PDF не печатается), отдельных полей приложений нет.

### Не сделано / вручную

- Ember-попап (превью обращения под шаблоном, вставка ссылки) в браузере не проверялся: нужен логин менеджера. CoffeeScript компилируется.
- Админка не открыта в браузере (нужен логин), проверена временным спеком с `render_views`.
- PDF реально отрисован wkhtmltopdf только через dev-сессию (19 KB, `%PDF-1.4`); вёрстку (шапка справа, линии, «Дата/Подпись» после текста) глазами не проверял.
- Rake-задачу после выкатки нужно запустить на каждом окружении один раз: `bundle exec rake operator_appeals:create_templates`.
