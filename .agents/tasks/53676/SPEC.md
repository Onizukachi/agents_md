# LT-53676 — Ссылки cookie-баннера и показ баланса кэшбэка в настройках партнёра

## Problem

Cookie-баннер («Мы собираем файлы cookie и применяем рекомендательные технологии, чтобы сайт работал
лучше») ведёт двумя ссылками на документы Level Travel — и делает это одинаково для всех партнёров.
Whitelabel Partner работает на своём домене и под своим брендом, но клиент такого партнёра всё равно
уходит по баннеру на юридические документы Level Travel. Подставить свои документы партнёру нечем.

Отдельно: партнёр не может управлять тем, показывать ли клиенту баланс кэшбэка/баллов в личном
кабинете. Такого переключателя нет ни в админке, ни в контракте настроек.

## Solution

Два документа cookie-баннера начинают резолвиться по тому же правилу Partner Document Override, что
уже действует для договоров и оферт: если для партнёра заведена статья с именем базового документа и
суффиксом `_<partner_id>`, баннер получает её, иначе — базовый документ Level Travel. Никаких новых
полей под URL в админке партнёра: переопределение — это заведение статьи в админке статей, а дефолт —
это отсутствие такой статьи. Поэтому и бэкфилла существующих партнёров не требуется.

Показ баланса — новый флаг на партнёре, выключенный по умолчанию, с чекбоксом в админке партнёра.

Обе настройки уезжают во фронт через `GET /papi/v3/partner/settings` — единственную ручку, из которой
WL-фронт забирает настройки веба.

## Current system state

**Ручка настроек.** `GET /papi/v3/partner/settings` → `Papi::V3::PartnerController#settings`
([app/controllers/papi/v3/partner_controller.rb:53](../../../app/controllers/papi/v3/partner_controller.rb#L53)).
Ответ целиком собирает `Partner::SettingsWebSerializer`
([app/serializers/partner/settings_web_serializer.rb](../../../app/serializers/partner/settings_web_serializer.rb)),
результат кладётся в `Rails.cache` на сутки под ключом
`api:partner:settings:#{ENV['PREPROD_SHOP_ID']}:#{@partner.id}`. Действие не ветвится по
`minor_version` — ответ одинаков для всех версий API.

`@partner` в PAPI определяется по токену авторизации, а не по домену
([app/controllers/papi/v3/papi_controller.rb:41-43](../../../app/controllers/papi/v3/papi_controller.rb#L41-L43)).

**Сброс кэша.** `Partner#delete_cache`
([app/models/partner.rb:234-245](../../../app/models/partner.rb#L234-L245)) чистит
`api:partner:settings:…` и `api:partner:wl_settings:…`, но только при сохранении самого партнёра и
только для WL. На изменения `Article` не реагирует ничто.

**Вторая, мобильная ручка.** `#wl_settings` в том же контроллере отдаёт
`Partner::SettingsSerializer` ([app/serializers/partner/settings_serializer.rb](../../../app/serializers/partner/settings_serializer.rb))
со своим, похожим, блоком `cashback`.

**Partner Document Override уже существует в трёх несогласованных копиях:**

- `AgreementContent.partner_agreement` ([app/base/agreement_content.rb:79-86](../../../app/base/agreement_content.rb#L79-L86)) —
  цепочка «активная на дату заказа → любая версия партнёрской статьи → дефолт»; гарда на WL нет,
  проверяется только наличие `partner_id`.
- `AgreementsListBuilder.determine_article_key` ([app/services/agreements_list_builder.rb:64-85](../../../app/services/agreements_list_builder.rb#L64-L85)) —
  `Article.active…exists?`, с гардом `return base_key unless partner&.wl?`.
- `ArticlesController#determine_order_agreement_code` / `#determine_extras_agreement_code`
  ([app/controllers/articles_controller.rb:116-132](../../../app/controllers/articles_controller.rb#L116-L132)) —
  то же, что у билдера.

**Хост документа.** `AgreementsListBuilder.domain_name` ([app/services/agreements_list_builder.rb:86-94](../../../app/services/agreements_list_builder.rb#L86-L94))
для WL отдаёт `https://#{partner.whitelabel_domain}`, иначе `DomainService.host_name`. Проверки на
пустой `whitelabel_domain` там нет, хотя колонка nullable. WL-домен обслуживается тем же приложением
(`ArticlesController` с `before_action :allow_subdomains`), так что `/articles/<name>` открывается и
на партнёрском домене.

**Статьи.** `Article.active` фильтрует по `start_date`/`end_date`
([app/models/article.rb:19-26](../../../app/models/article.rb#L19-L26)); версии — отдельные записи,
`ArticleSerializer` клеит `_ver_N` в URL при `version > 1`, `AgreementsListBuilder` — нет.
`recommendation_technologies_agreement` уже перечислен в `AgreementsListBuilder::ARTICLES`; локали
для обоих документов есть ([config/locales/ru.yml:4749-4751](../../../config/locales/ru.yml#L4749-L4751)).

**Существующий баннер в этом репозитории.** `client/lt-modules/src/components/Banners/CookiesBanner/`
хардкодит обе ссылки и отдельный кейс `isPartner('mosgortur')` в `constants.ts`. Ручку
`/papi/v3/partner/settings` этот фронт не потребляет.

**Фронтовый контракт.** `LevelTravel/lt-frontend#2081` уже описывает итоговый набор полей —
`legal_documents.cookie_policy_url`, `legal_documents.recommendation_technologies_url`,
`cashback.show_client_balance`; `personal_data_policy_url` там отсутствует. Оба новых узла
объявлены опциональными, внутренние поля — `string | null`.

**Документация PAPI.** У контроллера `partner` есть только
[docs/papi/v3/controllers/partner/3.0.yml](../../../docs/papi/v3/controllers/partner/3.0.yml).

**Прецеденты миграций на `partners`.** `add_column … :boolean, default: false, null: false` под гардом
`column_exists?`, без `safety_assured`
([db/migrate/20260415133000_add_deposit_allowed_to_partners.rb](../../../db/migrate/20260415133000_add_deposit_allowed_to_partners.rb),
[db/migrate/20260723083835_add_is_subagent_hybrid_to_partners.rb](../../../db/migrate/20260723083835_add_is_subagent_hybrid_to_partners.rb)).

## Scenarios

1. Партнёр без собственных статей запрашивает настройки — получает базовые документы Level Travel:
   `https://level.travel/articles/cookies_agreement` и
   `https://level.travel/articles/recommendation_technologies_agreement`.
2. Для Whitelabel Partner заведена активная статья `cookies_agreement_<id>` — в ответе стоит она,
   на домене партнёра. Вторая ссылка при этом остаётся базовой, на том же домене партнёра.
3. Whitelabel Partner без собственных статей — обе ссылки базовые, но на домене партнёра.
4. Whitelabel Partner с пустым `whitelabel_domain` — ссылки строятся от домена Level Travel, а не от
   пустого хоста.
5. Партнёрская статья существует, но неактивна (истёк `end_date` или `start_date` в будущем) —
   отдаётся базовый документ.
6. Не-WL партнёр, для которого всё же заведена статья `cookies_agreement_<id>` — override работает,
   хост при этом остаётся доменом Level Travel.
7. Флаг показа баланса выключен (состояние по умолчанию, включая всех существующих партнёров) — в
   ответе `false`.
8. Администратор включает флаг в админке партнёра — следующий ответ ручки отдаёт `true`.
9. Администратор заводит партнёрскую статью документа — ответ ручки меняется сразу, не дожидаясь
   истечения суточного кэша.

## Implementation decisions

**Резолвер ссылок.** Новый сервис под `Partner` отвечает за оба документа: по партнёру и имени
базового документа он возвращает абсолютный URL. Внутри — одно правило Partner Document Override:
существует ли активная `Article` с именем `<base>_<partner_id>`; если да — берётся она, если нет —
базовое имя. Фолбэка на неактивные версии нет, суффикс `_ver_N` в URL не добавляется: ссылка должна
вести на действующую редакцию документа и переживать выпуск новой версии без правок в настройках.

Override ищется для **любого** партнёра, без гарда на WL. Гард создавал бы невидимый отказ: документ
заведён, в админке статей виден, а в ручке не появляется.

Хост: домен Whitelabel Partner, если он непустой; во всех остальных случаях — домен Level Travel.
Пустой `whitelabel_domain` у WL-партнёра трактуется как «домена нет», потому что битая ссылка в
баннере на каждой странице хуже ссылки на наш домен.

Базовые имена документов — `cookies_agreement` и `recommendation_technologies_agreement`; они же
задают форму имени override и разбираются обратно при сбросе кэша.

**Флаг показа баланса.** Новая boolean-колонка `show_client_balance` на `partners`,
`default: false, null: false`; имя зеркалит поле контракта, чтобы не заводить слой перевода между
колонкой, сериализатором и разговором с фронтом. Миграция — по прецедентам выше, отдельного бэкфилла
не нужно: MySQL проставит дефолт существующим строкам.

Колонка добавляется в список разрешённых атрибутов админки. В форме партнёра — чекбокс рядом с
`bp_disabled` и **вне** ветки, скрывающей поля кэшбэка при `bp_disabled`: флаг про личный кабинет
независим от отключения блока кэшбэка, и скрытая связь между ними означала бы разбор «галка стоит, а
баланса нет». Лейбл — инлайновая строка, как у всех соседних полей формы. Значение попадает и в
`show`-страницу партнёра.

**Контракт ручки.** В веб-сериализаторе настроек появляются: узел `legal_documents` верхнего уровня с
`cookie_policy_url` и `recommendation_technologies_url`, и `show_client_balance` внутри
существующего блока `cashback`. Обе ссылки отдаются всегда непустыми строками — `null` в контракте
это страховка фронта, а не наше состояние, и фронту не нужна ветка «ссылки нет».

Мобильный сериализатор настроек не трогается: приложение cookie-баннер не показывает, а лишнее поле в
его контракте потом придётся выяснять, кто читает.

**Инвалидация кэша.** `Article` после коммита create/update/destroy сообщает резолверу об изменении;
резолвер разбирает имя статьи, и если это override одного из двух документов — чистит ключ настроек
соответствующего партнёра. Знание о ключах кэша PAPI остаётся в резолвере, модель `Article` о них не
знает. Ключи мобильных настроек не трогаются.

**Документация PAPI.** Правится существующий `3.0.yml` контроллера `partner`. Новый exact-version
файл не заводится: действие не ветвится по `minor_version`, поля поедут всем версиям, и отдельный
`3.16.yml` соврал бы, что до этой версии полей нет.

## Testing decisions

Два шва, оба существующие по типу:

1. **Резолвер ссылок** — юнит-спека на сервис. Здесь живут все ветки правила: базовый документ,
   активный override, неактивный override, WL-домен, WL с пустым доменом, не-WL с override. Проверяется
   строка URL целиком — внешний результат, а не то, каким запросом он получен. Прототип по форме —
   [spec/services/order/certificate_agreement_links_generator_spec.rb](../../../spec/services/order/certificate_agreement_links_generator_spec.rb):
   один `subject`, сравнение готовых ссылок.

2. **Ручка `GET /papi/v3/partner/settings`** — контроллерная спека. Сейчас её нет вовсе: в
   [spec/controllers/papi/v3/partner_controller_spec.rb](../../../spec/controllers/papi/v3/partner_controller_spec.rb)
   покрыт только `#wl_settings`. Спека проверяет, что оба новых узла присутствуют в теле ответа, и —
   отдельным сценарием — что заведение партнёрской статьи меняет ответ, несмотря на кэш. Второе важно
   именно потому, что сборка ответа целиком завёрнута в `Rails.cache.fetch`: без такого теста легко не
   заметить залипание. Инфраструктура готова: shared context `'papi'` и `'with cache enabled'` в
   [spec/controllers/papi/context.rb](../../../spec/controllers/papi/context.rb).

Фабрика `article` существует и позволяет задать `name`, `start_date`, `end_date`
([spec/factories/article.rb](../../../spec/factories/article.rb)).

Спеки пишутся по-английски (`describe`/`context`/`it`), по `rspec-style-guide`.

## Out of scope

- Cookie-баннер в этом репозитории (`client/lt-modules/.../CookiesBanner`) и его хардкод `mosgortur`.
  Это другой фронт; после выката override делает костыль `MGT_COOKIE_AGREEMENT` избыточным — кандидат
  в отдельный тикет.
- Добавление `cookies_agreement` в `AgreementsListBuilder::ARTICLES`: это добавило бы новый пункт в
  список соглашений в футере всех сайтов — видимое пользователям изменение, которого никто не заказывал.
- Сведе́ние трёх существующих копий Partner Document Override в одну реализацию.
- Кэш-ключ `agreement_links:…` в `AgreementsListBuilder` не содержит `partner_id`, из-за чего список
  соглашений протекает между партнёрами. Существующий баг, чинится не здесь; упомянуть в PR.
- Мобильная ручка `#wl_settings` и её сериализатор.
- Изменения в `lt-frontend`: контракт в PR #2081 уже верный. Фронту сообщается только, что ветка PR
  правит `openapi.3.13.yaml`, тогда как в main лежит `openapi.3.14.yaml`.

## Further notes

- Допущение без проверки: базовые статьи `cookies_agreement` и `recommendation_technologies_agreement`
  существуют в проде и активны. Косвенные подтверждения сильные (фронт хардкодит первую ссылку, вторая
  перечислена в `AgreementsListBuilder::ARTICLES`, для обеих есть локали), но прямой проверки не было —
  Redash недоступен. Локально нужные `Article` генерируются фабрикой.
- Термины **Whitelabel Partner** и **Partner Document Override** добавлены в `CONTEXT.md` (симлинк в
  `agents_md`) — изменение нужно закоммитить и запушить в `agents_md` отдельно, по DoD.
