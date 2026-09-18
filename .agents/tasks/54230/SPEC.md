# LT-54230 — Реквизиты владельца отеля в договоре по России

## Problem

В блоке «Сведения о туроператоре» договора для заказов типа «отель» по России сейчас
всегда печатаются реквизиты туроператора (юрлица-поставщика), хотя фактическая сторона
сделки для клиента в этом случае — владелец отеля. Формально это указывается через шаблон
Article вида `agreement_operator_info_78_operator_org_102`, но для внутрироссийских
отельных заказов такой текст вводит в заблуждение: клиенту показывают не того контрагента.
Данные о владельце отеля (`hotel_organizations`) для этого пока не хватает — там нет ОГРН
и адреса, только наименование, ИНН и телефон.

## Solution

Для заказов hotel-only по России, если у отеля есть засинканный из ФСА снапшот
`HotelOrganization`, договор вместо блока туроператора печатает короткий блок реквизитов
владельца отеля: наименование (в обе строки — «полное» и «сокращённое», так как ФСА не
разделяет эти формы), адрес, ИНН, ОГРН (если он есть — у ИП его в данных ФСА не бывает).
Ни реестровый номер РТО, ни блок финансового обеспечения не показываются — они относятся
только к туроператорам. Если снапшота ещё нет или фича выключена — печатается прежний
текст туроператора без изменений.

`hotel_organizations` дополняется столбцами `ogrn` и `address`, которые берутся из того же
живого запроса к ФСА, который уже выполняется ежедневно за каждым отелем (только
парсятся два дополнительных поля из уже получаемого ответа — новых запросов к ФСА не
добавляется). Логика создания нового снапшота при изменении данных расширяется на эти
два поля.

Фича переключается булевым флагом в `Settings` (`/admin/settings`) — можно выключить без
релиза, если после выкладки что-то пойдёт не так.

## Current system state

- `app/models/hotel_organization.rb` — `HotelOrganization`: `belongs_to :hotel`;
  `hotel, inn, name, phone_number, active_from` обязательны; `scope :latest_first`
  (`:17`) сортирует по `active_from desc, id desc`. Столбцов `ogrn`/`address` нет
  (`db/schema.rb:3730-3739`, миграция `db/migrate/20260626133423_create_hotel_organizations.rb`).
- `app/models/hotel.rb:66` — `has_many :hotel_organizations`.
- `app/workers/hotel_organizations/runner_worker.rb` — ежедневно в 1:00
  (`lib/schedule.rb:101`) перебирает `Hotel.unscoped.with_register_records` батчами по
  1000 и раздаёт `SyncWorker`.
- `app/workers/hotel_organizations/sync_worker.rb` — `sync_hotel` (`:19-24`) берёт
  `hotel.register_record['their_id']`, вызывает
  `Hotels::FsaHotelOrganizationFetcher#call`, и `create_organization_if_changed` (`:26-31`)
  создаёт новый снапшот, только если `organization_matches?` (`:33-39`, сравнивает
  inn/name/phone_number) вернул false.
- `app/services/hotels/fsa_hotel_organization_fetcher.rb` — живой запрос
  `GET https://tourism.fsa.gov.ru/api/v1/export/resorts/{their_id}/get` (сырой
  `Typhoeus.get`, в обход `ExternalRequest`). `build_attributes` (`:21-32`) берёт
  `hotel.main.ownerInn`, `hotel.main.ownerName`, `contacts.phone`; требует все три
  непустыми, иначе логирует и возвращает `nil`. По реальной VCR-кассете
  (`spec/fixtures/vcr_cassettes/hotels/fsa_hotel_organization_fetcher/success.yml`) в
  ответе также есть `hotel.main.ownerOgrn` (в этом примере — пустая строка, владелец —
  физлицо/ИП) и `hotel.main.addressList` — массив с одним элементом `{name: "<полный
  адрес>"}`, это адрес самого объекта размещения, а не отдельный юридический адрес
  владельца (в данных ФСА такого поля нет ни в одном из проверенных эндпоинтов).
- `fsa_registry_entries` (таблица из LT-53621, полное зеркало реестра ФСА, синк —
  `Fsa::RegistrySync`, ежедневно в 00:30, `lib/schedule.rb:491`) содержит те же по сути
  поля (`owner_inn`, `owner_ogrn`, `owner_name`, `addresses`), но собрана из другого
  (showcase) эндпоинта и намеренно изолирована — LT-53621 явно исключила из своего
  объёма любое обновление `Hotel`/matching/`register_record`. Телефона там нет вообще.
  Как источник для этой задачи не используется: не даёт данных, которых нет в уже
  выполняемом живом запросе, а вносит рассинхрон и лишнюю связность.
- `app/decorators/order_decorator.rb:5` — `delegate_all` (Draper), поэтому `package`,
  `country`, `object` доступны на декораторе напрямую.
- `app/decorators/order_decorator.rb:210-215` — `operator_info`: строит
  `OperatorAgreementManager.new(detected_operator, organization_id,
  package.operator_organization&.id)`, версию — через `operator_info_version`
  (`:482-490`), рендерит `agreement_manager.details(version)` через `$markdown.render`.
- `app/services/operator_agreement_manager.rb` — ищет `Article` по имени
  `agreement_operator_info_<operator_id>[...]_ver_<version>`, возвращает контент как есть.
- `app/base/agreement_content.rb:105-122` — `replace_placeholders` один раз проходит
  `gsub` по отрендеренному базовому шаблону (`agreement_order`/`partner_agreement_order_*`)
  и подставляет `order.send(placeholder_key)` на место каждого `{{placeholder_key}}`;
  `{{operator_info}}` подставляется значением `operator_info` целиком, без повторного
  сканирования на вложенные плейсхолдеры.
- `db/schema.rb:5284` — `packages.hotel_only` (boolean) → `package.hotel_only?`.
- `app/models/place.rb:55` — `Place::RUSSIA_ID = 225`; `app/models/order.rb:274` —
  `has_one :country, through: :hotel`; идиома проверки — `app/models/order.rb:3654-3656`
  (`insurance_info_code_name`): `country.id == Place::RUSSIA_ID`.
- `app/services/settings.rb` — `Settings::ATTRIBUTES` (`:2-9`), булевы читатели вида
  `def redirect_3ds_mode?; REDIS.static.with { |c| c.get('settings:redirect_3ds_mode') ==
  '1' }; end` (`:28-30`), `save` (`:37-49`) пишет их в Redis. Админ-страница
  `app/admin/settings.rb` (`ActiveAdmin.register_page "Settings"`, путь `/admin/settings`),
  форма — `app/views/admin/settings/_form.html.haml`.

## Scenarios

1. Заказ hotel-only по России, флаг включён, у отеля есть `HotelOrganization` с
   заполненным ОГРН — блок реквизитов показывает наименование (дважды — как «полное» и
   «сокращённое»), адрес, ИНН и ОГРН; текста туроператора и финобеспечения нет.
2. То же, но ОГРН у снапшота пустой (типичный случай для ИП) — строка ОГРН не
   выводится, остальной блок формируется как обычно.
3. Заказ hotel-only по России, флаг включён, но у отеля ещё нет ни одного
   `HotelOrganization` — печатается прежний текст (`OperatorAgreementManager`),
   поведение не меняется.
4. Заказ hotel-only по России, флаг выключен — печатается прежний текст независимо от
   наличия данных.
5. Заказ не hotel-only (тур) — поведение не меняется ни при каком состоянии флага.
6. Заказ hotel-only, но страна отеля не Россия — поведение не меняется.
7. Синк: живой ответ ФСА содержит непустые `ownerOgrn` и `addressList[0].name` — новый
   снапшот `HotelOrganization` сохраняет их в `ogrn`/`address`.
8. Синк: по сравнению с последним снапшотом изменился только `ogrn` или только
   `address` (inn/name/phone_number те же) — создаётся новый снапшот, а не пропускается.
9. Синк: `ogrn`/`address`/`inn`/`name`/`phone_number` совпадают с последним снапшотом —
   новый снапшот не создаётся (текущее поведение дедупликации не ломается).
10. Синк: `ownerOgrn` в ответе ФСА пустой — снапшот всё равно создаётся (пустой ОГРН не
    входит в проверку обязательных полей, как сейчас для inn/name/phone).

## Implementation decisions

**Миграция.** В `hotel_organizations` добавляются nullable `ogrn:string` и
`address:string`. Валидация presence на них не заводится — как и в данных ФСА, значение
может отсутствовать. Переводы атрибутов добавляются в `config/locales/ru.yml`
(`activerecord.attributes.hotel_organization`).

**Извлечение данных.** `Hotels::FsaHotelOrganizationFetcher#build_attributes`
дополнительно читает `ogrn` из `hotel.main.ownerOgrn` и `address` из первого элемента
`hotel.main.addressList` (`.name`). Оба поля не входят в проверку «все обязательные
атрибуты присутствуют» — как сейчас для inn/name/phone, синк должен проходить и при
пустом ОГРН/адресе.

**Обновление при синхронизации.** `HotelOrganizations::SyncWorker#organization_matches?`
расширяется сравнением по `ogrn` и `address` — новый снапшот создаётся при изменении
любого из пяти полей (inn, name, phone_number, ogrn, address), а не только первых трёх.

**Вывод в договор.** В `OrderDecorator#operator_info` добавляется ранняя ветка:
если заказ подходит (`package.hotel_only?`, `country&.id == Place::RUSSIA_ID`,
флаг `Settings` включён) и у отеля пакета есть хотя бы один `HotelOrganization`
(берётся самый свежий — `latest_first.first`, та же семантика, что уже используется
в `SyncWorker`), метод возвращает блок реквизитов владельца отеля вместо результата
`OperatorAgreementManager`. Иначе (нет данных, флаг выключен, заказ не подходит под
условия) — поведение метода не меняется. `OperatorAgreementManager`/поиск Article в
новой ветке не участвует — это самостоятельный путь рендеринга, без шаблонов.

Состав блока: полное наименование и сокращённое наименование — оба равны
`hotel_organization.name`; адрес (место нахождения) — `hotel_organization.address`;
ИНН — `hotel_organization.inn`; ОГРН — `hotel_organization.ogrn`, строка полностью
опускается, если пусто. Точная русскоязычная формулировка заголовка и подписей строк —
предмет согласования с постановщиком/FinDoc на этапе реализации, в спеке не фиксируется.

**Feature flag.** Новый ключ в `Settings::ATTRIBUTES`, например
`hotel_owner_requisites_in_agreement`, булевый читатель по образцу
`redirect_3ds_mode?`, чекбокс в `app/views/admin/settings/_form.html.haml`.

## Testing decisions

Расширяем существующие спеки, новых файлов и швов не заводим.

1. **Извлечение полей.** `spec/services/hotels/fsa_hotel_organization_fetcher_spec.rb` —
   `expected_attributes` дополняется `ogrn`/`address` по реальной VCR-кассете; кассета
   уже содержит `ownerOgrn: ""` и `addressList`, значит сценарий 10 (пустой ОГРН)
   проверяется тем же основным тестом без отдельной кассеты.
2. **Обновление снапшота.** `spec/workers/hotel_organizations/sync_worker_spec.rb` —
   существующие тесты «creates a new organization when latest values differ» /
   «does not create organization when latest values match» дополняются кейсами, где
   отличается/совпадает именно `ogrn`/`address` при равенстве остальных полей.
3. **Рендер в договоре.** `spec/decorators/order_decorator_spec.rb` — новый
   `describe '#operator_info'`, в стиле `header_for_client` (декоратор + `double`/
   `receive_messages` на `package`, `country`, флаг), покрывает сценарии 1-6: блок
   реквизитов при подходящих условиях (с ОГРН и без), и три ветки отказа в старое
   поведение (нет данных, флаг выключен, заказ не hotel-only/не Россия) — для них
   достаточно проверить, что вызывается прежний путь через `OperatorAgreementManager`
   (например, стабом), не рендеря сами Article.

Валидации новых колонок (`spec/models/hotel_organization_spec.rb`) отдельно не
тестируются — presence на них не заводится, стандартных матчеров не требуется.
`Settings`-флаг отдельной спекой не покрывается: у класса `Settings` нет ни одной
спеки в проекте, соответствующее поведение проверяется через ветки в спеке декоратора.

## Out of scope

- Общий распределённый rate limiter/`ExternalRequest` для
  `Hotels::FsaHotelOrganizationFetcher` и `Hotels::RosreestrFsaUpdater` — известный
  пробел (`ExternalApiRateLimiter` из LT-53621 подключён только к `Fsa::Client`,
  `RosreestrFsaUpdater` вообще бьёт в тот же эндпоинт 10 параллельными запросами), но
  явно не эта задача.
- Использование `fsa_registry_entries`/`Fsa::RegistrySync` как источника данных — решение
  принято против, обоснование в «Current system state».
- КПП, организационно-правовая форма и любые другие реквизиты, которых нет в данных
  ФСА ни на одном из проверенных эндпоинтов.
- Проверка того, что адрес объекта размещения из ФСА совпадает с юридическим адресом
  владельца — данных для такой проверки у нас нет, поле используется «как есть» по
  решению постановщика.
- Изменения в `Article`/ActiveAdmin-шаблонах, соглашении об именовании
  `agreement_operator_info_*` — новая ветка их не использует и не расширяет.
- Прочие поля живого ответа ФСА (категория, тип размещения, статус и т.д.) —
  не извлекаются, не нужны для этой задачи.

## Further notes

- ФСА отдаёт для владельца одну строку наименования без деления на полное/сокращённое
  (в отличие от отеля самого — там `fullName`/`shortName` есть, но это имя объекта
  размещения, не владельца). Решение показывать одно и то же значение в обеих строках
  подтверждено постановщиком в разговоре, дальнейшего уточнения не требует.
- ОГРН в данных ФСА часто пуст для ИП (нет аналога — ОГРНИП там не публикуется вовсе).
- Адрес, который в итоге попадёт в договор, — адрес объекта размещения (гостиницы) из
  реестра ФСА, а не отдельно подтверждённый юридический адрес владельца; трактовка «это
  и есть нужный адрес» — осознанное решение постановщика, а не техническое ограничение,
  которое можно снять другим источником данных (такого источника в проверенных FSA API
  не существует).

## Progress log

Реализовано как единая задача (тикеты не заводились).

- Миграция `AddOgrnAndAddressToHotelOrganizations` (`up`/`down` + `column_exists?`-гарды,
  без `safety_assured` — добавление nullable string-колонок не требует его). Применена
  в dev и test БД; `db/schema.rb` вручную сведён к трёхстрочному диффу (версия + два новых
  поля в `hotel_organizations`) после того, как локальный дампер переформатировал весь
  файл из-за дрейфа версии MySQL/Rails — тот же приём, что в LT-53619.
- `Hotels::FsaHotelOrganizationFetcher#build_attributes` переименовал внутреннюю
  переменную в `required_attributes` и отдельно домешивает `ogrn`/`address`
  (`hotel.main.ownerOgrn`, первый элемент `hotel.main.addressList[].name`) через
  `.presence`, не участвуя в проверке «все обязательные поля присутствуют».
- `HotelOrganizations::SyncWorker#organization_matches?` расширен сравнением по
  `ogrn`/`address` — пять полей вместо трёх.
- `Settings` получил `hotel_owner_requisites_in_agreement?` (по образцу
  `redirect_3ds_mode?`) и чекбокс в форме `/admin/settings` под новым заголовком
  «Договоры».
- `OrderDecorator#operator_info` — ранняя ветка `hotel_owner_requisites?` (флаг +
  `package.hotel_only?` + `country&.id == Place::RUSSIA_ID` + наличие снапшота у
  `package.hotel.hotel_organizations.latest_first.first`), рендерящая
  `hotel_owner_requisites` вместо пути через `OperatorAgreementManager`. Формирование
  строк вынесено в `hotel_owner_requisites_lines` отдельным приватным методом — иначе
  `hotel_owner_requisites` превышал лимит `Metrics/MethodLength` в 10 строк. Адрес,
  как и ОГРН, выводится только если присутствует (в спеке явно зафиксирован только
  ОГРН как опциональный, но `address` — такая же nullable-колонка без presence-валидации
  при создании снапшота, поэтому решил не печатать пустую строку «Адрес: » и для него —
  расширение того же правила, а не отступление от спеки).
- Заголовок блока и подписи строк («СВЕДЕНИЯ О ВЛАДЕЛЬЦЕ ОТЕЛЯ», «Полное наименование»,
  «Сокращенное наименование», «Адрес (место нахождения)», «ИНН», «ОГРН») — черновая
  формулировка по образцу блока туроператора из скриншота тикета; финальная
  редакция текста, как и оговорено в спеке, — на усмотрение постановщика/FinDoc.
- I18n: `activerecord.attributes.hotel_organization.{ogrn,address}` в `config/locales/ru.yml`,
  рядом с существующим блоком `hotel:` — только для двух новых полей, остальные
  атрибуты `HotelOrganization` переводов не имели и раньше, трогать не стал.
- Тесты — три существующих шва расширены, новых спек-файлов не заводилось:
  - `spec/services/hotels/fsa_hotel_organization_fetcher_spec.rb` — `expected_attributes`
    дополнен `ogrn: nil` и реальным адресом из той же VCR-кассеты (кассета
    сама по себе уже покрывает сценарий «ОГРН пустой»).
  - `spec/workers/hotel_organizations/sync_worker_spec.rb` — `organization_attributes`
    дополнен ogrn/address; два новых теста «creates a new organization when only
    ogrn/address differs».
  - `spec/decorators/order_decorator_spec.rb` — новый `describe '#operator_info'`,
    6 примеров (успешный рендер, пустой ОГРН, флаг выключен, нет снапшота, не
    hotel-only, не Россия). Для success-кейса используется реальные `create(:hotel)`/
    `create(:hotel_organization)` вместо дублирующего double на relation — так
    отработал настоящий scope `latest_first`, и заодно ушли rubocop-замечания
    `RSpec/VerifiedDoubles`/`RSpec/MultipleMemoizedHelpers`, которые вылезли на
    первой версии теста с `double(latest_first: ...)`.
- Rubocop прогнан по всем новым/изменённым файлам. В новом коде поправил две реальные
  находки (лишняя trailing comma в литерале массива, метод длиннее 10 строк — вынес
  построение строк в отдельный метод). Остальные замечания в затронутых файлах —
  предсуществующие паттерны того же файла (например, `Style/GlobalVars` на
  `$markdown.render`, уже используемый в оригинальном `operator_info`;
  `RSpec/SubjectStub`/`RSpec/MultipleExpectations` в `header_for_client`/
  `description_for_client`/`agreement_operator_extras_price` — не трогал, это
  ушло бы за рамки задачи).
- Полный прогон задетых спек (первый проход, до review-гейта):
  `spec/models/hotel_organization_spec.rb`,
  `spec/services/hotels/fsa_hotel_organization_fetcher_spec.rb`,
  `spec/workers/hotel_organizations/`, `spec/decorators/order_decorator_spec.rb`,
  `spec/services/operator_agreement_manager_spec.rb` — 36 примеров, 0 падений,
  1 pending (предсуществующий `xit` в `operator_agreement_manager_spec.rb`, не
  относится к этой задаче).

### Review gate (`leveltravel-pr-review`)

Прогнан один раз на всю задачу (uncommitted-диф, base — локальный `develop`
`45027ac1...`). Native-проход (codex CLI) фактически не смог посмотреть рабочее
дерево — в этом окружении у него не было доступа к локальному shell, поэтому
вместо `git diff` он сравнил два *чужих* коммита на GitHub через MCP (ни один из
них не содержит изменений этой задачи, так как ничего не закоммичено) и вернул
пустой результат. Такой вывод недостоверен, поэтому native-проход заменён на
fallback-агента (standard-agent fallback, с явной пометкой), которому вручную
указано читать именно локальный рабочий каталог. Independent focused-companion
проход шёл параллельно как обычно.

Companion на первом прогоне вернул BLOCKED с одним CONCERN и двумя NIT:
- **CONCERN** (реальный, подтверждён): `Hotels::FsaHotelOrganizationFetcher#build_attributes`
  после правки превысил `Metrics/MethodLength`/`Metrics/AbcSize` — я срезал rubocop-вывод
  через `tail -20` и не увидел эти замечания при первой самопроверке. Исправлено вынесением
  `required_attributes(data)`/`optional_attributes(data)` в приватные методы (0 замечаний
  после фикса).
- **NIT**: тест «когда ОГРН пуст» проверял только отсутствие строки ОГРН, не проверяя,
  что остальной блок (имя/адрес/ИНН) при этом рендерится нормально — то есть фактически
  не покрывал сценарий 2 из спеки целиком. Исправлено — тест теперь также утверждает
  наличие имени/адреса/ИНН.
- **NIT**: у новых колонок `ogrn`/`address` не было `length`-валидации, в отличие от
  соседних `inn`/`phone_number`/`name` — при значении длиннее лимита БД `create!` в
  `SyncWorker` (retry: false) просто упал бы без ретрая. Исправлено:
  `validates :inn, :phone_number, :ogrn, length: { maximum: 255 }`,
  `validates :name, :address, length: { maximum: 512 }`; заодно расширил саму колонку
  `address` в БД до `limit: 512` (как у `name`), а не оставил на дефолтных 255 —
  миграция была откачена и переприменена внутри контейнера, `db/schema.rb` заново
  вручную сведён к минимальному диффу.

После фиксов companion перепроверил все три пункта заново (сам прогнал rubocop и
спеки, сверил байт-в-байт остальные файлы) и дал **PASS**. Fallback-агент на
финальном дереве тоже дал **PASS**: 0 BLOCKER, 0 CONCERN, 3 NIT — все приняты как
есть, без исправлений:
1. Пропуск строки адреса при пустом `address` — в спеке явно оговорен только пропуск
   ОГРН; расширение того же правила на адрес осознанное и безвредное, но не было
   отдельного теста на этот конкретный случай (пустой адрес) — оставлено как есть,
   слишком мелкий кейс для отдельного покрытия.
2. Спека модели не проверяла новые `length`-валидации — закрыто отдельным фиксом
   после companion-прохода: `validate_length_of(:ogrn).is_at_most(255)` и
   `validate_length_of(:address).is_at_most(512)` в `hotel_organization_spec.rb`.
3. Первый прод-прогон `RunnerWorker` после релиза создаст новый снапшот почти для
   каждого отеля с непустым `ogrn`/`address` в ответе ФСА, так как все существующие
   строки сейчас имеют эти поля `nil` — это ожидаемое разовое пополнение данных, а не
   дефект.

Финальный прогон после всех правок ревью: 38 примеров, 0 падений, 1 pending
(тот же предсуществующий `xit`).

- Не делалось (сознательно, по решениям выше): rate limiter/`ExternalRequest` для
  `Hotels::FsaHotelOrganizationFetcher`, коммит и пуш изменений — ждут отдельного
  запроса.
