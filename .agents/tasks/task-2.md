# LT-52426: загрузчик реестров оплат Островка

## 1. Бизнес-контекст

- Островок передаёт реестр оплат в формате XLSX.
- Реестр загружается через существующую страницу `/admin/operations_loader` как новый поставщик.
- Процесс построен по аналогии с Gortravel: сохранение файла, асинхронное извлечение операций, обогащение через Dynamics, поиск заказа и создание операторского платежа.
- Пример входного файла: `/Users/hikaru/Downloads/invoice-389135-00001.xlsx`.

## 2. Итоговый процесс обработки

1. Пользователь выбирает `Ostrovok` в `/admin/operations_loader` и загружает XLSX.
2. `Accounting::OperationsLoader::FileProcessor` формирует файл для обработки и сохраняет его в `AccountingFile`.
3. Запускается `Accounting::OperatorProcessorWorker` с `supplier_name = Ostrovok`, именем файла и `report_id`.
4. `Accounting::OperatorOperationsProcessor` последовательно выполняет стадии `extract`, `enrich`, `manage`.
5. `Accounting::Ostrovok::Extractor` читает строки и создаёт `OperatorOperation` с логами обработки.
6. `Accounting::Ostrovok::Enricher` получает booking ID через Dynamics и ищет заказ.
7. Для сопоставленных операций создаются или обновляются операторские платежи заказа.
8. Созданный/изменённый `OperatorPayment` записывается в `OperatorOperation`.

## 3. Согласованные идентификаторы

| Назначение | Значение |
| --- | --- |
| Оператор операции | `operator_id = 78` |
| Поставщик `OperatorOperation` | `supplier_id = 102` |
| Поставщик при поиске заказа | `operator_organization_id = 89` |
| Организация создаваемого/искомого ОП | `operator_organization_id = 89` |
| Организация запроса в Dynamics | `organization_id = 8` |
| Валюта | `RUB` |

- Комбинация `operator_78_supplier_102` однозначно определяет `Ostrovok`.
- Комбинация `operator_78_supplier_89` продолжает однозначно определять `Gortravel`.
- Проверка `package.misc_data[:acm_supplier_id]` удалена по решению бизнеса и не участвует в сопоставлении.
- В production организация `OperatorOrganization#102` уже существует.
- Локально была создана организация `#102` со значениями:
  - `inn = 7703403951`;
  - `name = ООО 'Агентика Тревэл'`;
  - `phone = +7(926) 391-2299`;
  - `operator_id = 78`;
  - `active = true`;
  - `main = false`.

## 4. Маппинг XLSX

| Колонка XLSX | Поле `OperatorOperation` | Использование |
| --- | --- | --- |
| `Paid, total` | `gross_captured_amount` | Сумма списания в операторском платеже |
| `Total price b2b2c` | `captured_amount` | Расход без АК, хранится в операции |
| `Refund amount` | `gross_refunded_amount` | Сумма возврата в операторском платеже |
| `Сreated on` | `operation_time` | Время операции до секунды |
| `Order #` | `supplier_order_id` | ID заказа у поставщика |

- Первая буква в исходном заголовке `Сreated on` — кириллическая `С`.
- Все денежные значения приводятся к положительному `Decimal`.
- Строка с положительным `Paid, total` создаёт оплату.
- Строка с положительным `Refund amount` создаёт возврат.
- Если в строке одновременно есть оплата и возврат, она разделяется на две операции с разными `operation_type`.
- В приложенном примере один лист и 25 строк; все 25 строк являются оплатами, возвратов нет.

## 5. Защита от повторной загрузки

- `external_id` рассчитывается как SHA-256 от имени поставщика и нормализованных бизнес-полей строки.
- Идентификатор не зависит от имени файла и порядка строк.
- Для строки «оплата + возврат» обе операции имеют одинаковый SHA-256, но отличаются по `operation_type`.
- `OperatorOperation.create_record` ищет существующую запись по `external_id`, `operator_id`, `supplier_id` и `operation_type`.
- Последовательная повторная загрузка не создаёт новые операции.
- При повторной загрузке старые операции не получают новый `report_id`, поэтому обработка нового отчёта может завершиться сообщением «Нет подходящих операций для выполнения действия». Это ожидаемое следствие текущей дедупликации.

### Открытый риск из PR review

- Защита не является атомарной при конкурентной обработке: используется `find_or_create_by`, а индекс `operator_operations.external_id` не уникальный.
- Два одновременно работающих задания с одинаковыми строками, но разными аргументами/`report_id`, теоретически могут создать дубли операций и ОП.
- Рекомендованное продолжение: проверить production на существующие дубли, добавить составной уникальный индекс по `external_id`, `operator_id`, `supplier_id`, `operation_type` и обработать `ActiveRecord::RecordNotUnique`.
- Для такой доработки обязательно использовать skill `leveltravel-migrations`.

## 6. Поиск и обогащение заказа

- Dynamics вызывается по `supplier_order_id` с `organization_id = 8`.
- Полученный booking ID сохраняется в `operator_booking_id`.
- Основной поиск заказа выполняется через `Order.by_operator_booking_id` по:
  - booking ID из Dynamics;
  - `operator_id = 78`;
  - `operator_organization_id = 89`.
- Общий `DynamicsEnricher` получил переопределяемый метод `order_supplier_id`; для остальных поставщиков он возвращает исходный `operation.supplier_id`.
- Для Островка `order_supplier_id` возвращает `89`.
- Дополнительной проверки `acm_supplier_id` больше нет; остаются стандартные проверки Dynamics на booking ID, заказ, валюту и курс.

## 7. Создание и возврат операторских платежей

- Операция Островка определяется по `supplier_id = 102`.
- ОП создаётся и ищется с `operator_organization_id = 89`.
- Для оплаты сумма `captured_amount` и `requested_amount` ОП берётся из `gross_captured_amount` операции.
- Для возврата сумма берётся из `gross_refunded_amount` операции.
- ОП создаётся как депозитный: `deposit = true`, `payment_order = false`, `virtual = false`.
- Логика gross-сумм применяется только к операциям Островка; остальные поставщики продолжают использовать обычные `captured_amount` и `refunded_amount`.
- Отмена возврата Островка также использует `gross_refunded_amount`.

## 8. Изменения загрузчика и ActiveAdmin

- После merge с `develop` списки поставщиков берутся из `Accounting::Constants::LOADER_SUPPLIERS`.
- `Ostrovok` добавлен в:
  - `operations_loader`;
  - `operations_loader_filter`.
- Поставщики `Anex` и `FunSun`, добавленные в `develop`, полностью сохранены.
- В `FileProcessor` строки XLSX записываются с типом `:string`. Это исправило ошибку Axlsx `invalid value for Integer(): "2026-07-05T23:39:40"`.
- Извлечение внутреннего booking ID теперь безопасно возвращает `nil`, если в формате поставщика нет `operator_booking_id` или `order_id`.
- В `app/admin/operator_operations.rb` снят фильтр `operator_organizations.active = true`.
- Фильтр `operators.enabled = true` сохранён, поэтому в реестре теперь видны операции неактивных организаций активных операторов.

## 9. Основные изменённые файлы

- `app/services/accounting/constants.rb`
- `app/services/accounting/ostrovok/extractor.rb`
- `app/services/accounting/ostrovok/enricher.rb`
- `app/services/accounting/ostrovok/file_uploader.rb`
- `app/services/accounting/dynamics_enricher.rb`
- `app/services/accounting/operations_loader/file_processor.rb`
- `app/models/concerns/operator_operations/common.rb`
- `app/models/concerns/operator_operations/capture_methods.rb`
- `app/models/concerns/operator_operations/refund_methods.rb`
- `app/models/concerns/operator_operations/cancel_methods.rb`
- `app/models/operator_payment.rb`
- `app/admin/operator_operations.rb`
- `spec/models/operator_operation_spec.rb`
- `spec/services/accounting/ostrovok/enricher_spec.rb`
- фабрики `OperatorOperation` и `OperatorOrganization`.

## 10. Merge с develop

- В feature-ветку влит актуальный `origin/develop` merge-коммитом `2b5f9376d7`.
- Конфликты были в:
  - `app/admin/operator_operations/operations_loader.rb`;
  - `app/admin/operator_operations/operations_loader_filter.rb`;
  - `app/services/accounting/constants.rb`.
- При разрешении конфликтов максимально сохранена архитектура `develop`: централизованный `LOADER_SUPPLIERS`, новые поставщики и переименование загрузчика заявок.
- Последнее изменение удаления ACM-проверки и фильтра active зафиксировано коммитом `9bc9e907e6`.

## 11. Проверки

- После merge выполнен focused-прогон:
  - `spec/services/accounting/ostrovok/enricher_spec.rb`;
  - `spec/models/operator_operation_spec.rb`;
  - `spec/services/accounting/operator_operations_processor_spec.rb`;
  - `spec/services/accounting/gortravel_anex/enricher_spec.rb`.
- Результат после merge: `40 examples, 0 failures`.
- После удаления ACM-проверки: `38 examples, 0 failures`.
- Приложенный XLSX дополнительно разобран текущим extractor без записи операций:
  - 25 строк;
  - 25 оплат;
  - 0 возвратов;
  - `operation_time` сохраняется строкой ISO до присваивания ActiveRecord;
  - первая строка: `captured_amount = 2435`, `gross_captured_amount = 2405`, `supplier_id = 102`.
- `git diff --check` проходил без ошибок.
- Полный TeamCity CI-equivalent прогон локально не выполнялся.

## 12. Текущее состояние и следующие шаги

- [x] Добавить Островок в интерфейс загрузки реестров.
- [x] Реализовать constants/extractor/enricher/file uploader.
- [x] Сохранить файл в `AccountingFile` и передавать `report_id` в воркер.
- [x] Реализовать стабильный SHA-256 для последовательной дедупликации.
- [x] Искать заказ через оператора `78` и организацию `89`.
- [x] Создавать операции с поставщиком `102`.
- [x] Создавать и искать ОП с организацией `89`.
- [x] Использовать gross-суммы для списания и возврата.
- [x] Исправить обработку времени ISO в промежуточном XLSX.
- [x] Сохранить изменения `develop` при разрешении конфликтов.
- [x] Удалить проверку `acm_supplier_id`.
- [x] Показывать операции неактивных организаций в ActiveAdmin.
- [ ] Добавить отдельный spec для `Accounting::Ostrovok::Extractor`: XLSX, возврат, двойная строка, неверные заголовки, пустые суммы и дедупликация.
- [ ] Согласовать и реализовать атомарную защиту от конкурентных дублей.
- [ ] Перед финальным выпуском выполнить полный CI/TeamCity прогон.

## 13. Заметки для восстановления сессии

- Рабочая ветка: `feature/LT-52426-operator-operations-loader-support-ostrovok`.
- Базовая ветка PR: `develop`.
- Не возвращать старые идентификаторы Островка `72/24`: финальные значения операции — `78/102`.
- Не добавлять обратно проверку `acm_supplier_id`: бизнес подтвердил, что она не нужна.
- Заказ и ОП намеренно используют организацию `89`, хотя сама `OperatorOperation` использует поставщика `102`.
- При следующей доработке начать с решения по уникальному индексу и тестов extractor.
