# Задача: перенести маппинг динамики на туроператоров в админку

## 1. Бизнес контекст для задачи

- Сейчас маппинг внешних `dynamic_operator_id` на внутренних туроператоров хранится в коде как `OperatorOrganization::EXTERNAL_DYNAMIC_IDS`.
- Этот маппинг влияет на определение оператора и юрлица для динамических пакетов, в том числе в `Package`, `OrderDecorator` и `OrderSync::Adapters::Leveltravel`.
- Бизнесу нужен управляемый через админку справочник, чтобы менять соответствия без правки константы и деплоя.
- При этом нельзя потерять текущее поведение: существующие соответствия должны быть перенесены в БД, а константа может остаться как fallback на переходный период.

## 2. Ключевые решения и обоснования

- Вынести соответствия в отдельную модель `ExternalDynamicMatching` с таблицей `external_dynamic_matchings`.
  Обоснование: это отдельный справочник с простой ответственностью "внешний оператор динамики -> внутренний оператор", его не нужно смешивать с `OperatorOrganization`.
- Оставить `OperatorOrganization::EXTERNAL_DYNAMIC_IDS` как fallback, но перевести чтение маппинга на единый источник через модель/метод доступа.
  Обоснование: это позволит безопасно ввести админку и миграцию данных без регресса для уже работающих сценариев.
- Добавить отдельный ActiveAdmin-ресурс для CRUD по справочнику.
  Обоснование: задача про перенос настройки в админку, поэтому изменение должно быть доступно операционно и без консоли.
- Для выбора `operator_id` в форме использовать `selectize` с label вида `"#{name} (#{id})"`.
  Обоснование: операторов удобнее искать по названию, но ID нужен для однозначной идентификации.
- Перенос значений из константы сделать отдельной rake task, а не data migration.
  Обоснование: пользователь явно просит rake task; это также позволяет повторно и осознанно запускать перенос отдельно от схемы.
- Проверить все текущие места чтения `EXTERNAL_DYNAMIC_IDS` и перевести их на новую точку доступа с fallback.
  Обоснование: иначе часть приложения продолжит читать только константу и админская настройка не начнет реально влиять на поведение.

## 3. Структурированный список задач

- [ ] Шаг 1: Найти все текущие места использования `OperatorOrganization::EXTERNAL_DYNAMIC_IDS` и определить единую точку чтения маппинга.
- [ ] Шаг 2: Сгенерировать миграцию для создания таблицы `external_dynamic_matchings` по проектным правилам (`up/down`, `if_not_exists`, безопасный rollback).
- [ ] Шаг 3: Реализовать модель `ExternalDynamicMatching` с ассоциацией на `Operator`, базовыми валидациями присутствия и понятным методом поиска по `dynamic_operator_id`.
- [ ] Шаг 4: Добавить в код единый слой доступа к маппингу, который сначала ищет запись в БД, а при отсутствии использует `OperatorOrganization::EXTERNAL_DYNAMIC_IDS` как fallback.
- [ ] Шаг 5: Перевести `Package`, `OrderDecorator`, `OrderSync::Adapters::Leveltravel` и другие найденные места на новый слой доступа.
- [ ] Шаг 6: Создать отдельный ActiveAdmin-ресурс для `ExternalDynamicMatching` с index/filter/form/show и `selectize`-селектором оператора в формате `"#{name} (#{id})"`.
- [ ] Шаг 7: Добавить rake task для заполнения `external_dynamic_matchings` значениями из константы с безопасным повторным запуском.
- [ ] Шаг 8: Запустить миграцию, обновить `db/schema.rb`, загрузить test schema и проверить, что схема изменилась только в рамках задачи.
- [ ] Шаг 9: Добавить или обновить тесты на новый источник маппинга, fallback на константу и критичные сценарии, где определяется оператор динамики.
- [ ] Шаг 10: Прогнать релевантные тесты по изменённым областям и зафиксировать результат перед следующим этапом работы.

## 4. Заметки для восстановления сессии

### Текущее состояние проекта и уже выполненная работа

- Изучен текущий источник данных: `EXTERNAL_DYNAMIC_IDS` объявлен в [app/models/operator_organization.rb](/home/hikaru/projects/work/leveltravel/app/models/operator_organization.rb:1).
- Найдены как минимум три прямых использования константы:
  - [app/models/package.rb](/home/hikaru/projects/work/leveltravel/app/models/package.rb:1308)
  - [app/decorators/order_decorator.rb](/home/hikaru/projects/work/leveltravel/app/decorators/order_decorator.rb:467)
  - [app/apis/order_sync/adapters/leveltravel.rb](/home/hikaru/projects/work/leveltravel/app/apis/order_sync/adapters/leveltravel.rb:91)
- Проверены примеры `selectize` в ActiveAdmin и подтверждено, что в проекте это стандартный паттерн для выбора связанных сущностей.
- Проверена папка `.agents/tasks`: numbered task-файлов ещё не было, поэтому создан первый артефакт `task-1.md`.
- Из migration-инструкций проекта зафиксировано:
  - миграции создавать генератором, не руками;
  - использовать `up/down`, `if_not_exists`, `if_exists`, `safety_assured`, безопасные index helpers;
  - команды Rails выполнять через `source ./lt.sh`, затем `lt sh`.
- Реализация выполнена:
  - добавлена миграция [db/migrate/20260708154346_create_external_dynamic_matchings.rb](/home/hikaru/projects/work/leveltravel/db/migrate/20260708154346_create_external_dynamic_matchings.rb:1);
  - добавлены модель [app/models/external_dynamic_matching.rb](/home/hikaru/projects/work/leveltravel/app/models/external_dynamic_matching.rb:1), admin-ресурс [app/admin/external_dynamic_matchings.rb](/home/hikaru/projects/work/leveltravel/app/admin/external_dynamic_matchings.rb:1) и rake task [lib/tasks/external_dynamic_matchings.rake](/home/hikaru/projects/work/leveltravel/lib/tasks/external_dynamic_matchings.rake:1);
  - чтение маппинга переведено на БД с fallback на константу в `Package`, `OrderDecorator` и `OrderSync::Adapters::Leveltravel`;
  - добавлены тесты на модель, rake task и путь в `Package`;
  - миграция проверена через `db:migrate`, `db:rollback STEP=1`, повторный `db:migrate`;
  - `db/schema.rb` вручную очищен до минимального diff по задаче, потому что локальный `db:migrate` подтянул шум от чужих pending migration и сломал `db:test:load`.
- Локальная проверка завершена успешно:
  - `bundle exec rails db:test:load`
  - `bundle exec rspec spec/models/external_dynamic_matching_spec.rb spec/models/package_spec.rb spec/lib/tasks/external_dynamic_matchings_rake_spec.rb`
- Синхронизация `.agents` в `../agents_md` не завершена: mirror-репозиторий прошёл базовую проверку, но `git -C ../agents_md pull --ff-only` на ветке `main` упал с `fatal: Not possible to fast-forward, aborting.` из-за divergence. Это внешний блокер, не связанный с кодом задачи.

### Критически важные принятые решения

- Таблица должна быть отдельной, а не расширением `operator_organizations`, потому что хранит самостоятельный справочник соответствий.
- Константа не удаляется сразу, а остаётся fallback-источником до завершения перехода.
- Перенос исходных значений выполняется rake task-ом, а не data migration.
- Внедрение должно идти через единую точку чтения маппинга, чтобы не размазывать логику по нескольким классам.

### Точка, с которой нужно продолжить, если сессия прервется

- Следующий шаг при возобновлении: либо починить расхождение ветки `main` в `../agents_md`, либо согласовать с пользователем, что sync можно сделать отдельно.
- Кодовую часть задачи продолжать не нужно, если не появятся замечания после ручной проверки админки.
- Для завершения документационного хвоста:
  - в `../agents_md` сначала привести `main` к состоянию, где `git pull --ff-only` проходит;
  - затем повторить `rsync -a AGENTS.md .agents/ ../agents_md/`, `git -C ../agents_md add AGENTS.md .agents`, commit и push.
- Если понадобится повторная локальная проверка после правок:
  - `source ./lt.sh`
  - `lt sh`
  - `bundle exec rails db:migrate`
  - `bundle exec rails db:test:load`
  - `bundle exec rspec spec/models/external_dynamic_matching_spec.rb spec/models/package_spec.rb spec/lib/tasks/external_dynamic_matchings_rake_spec.rb`
