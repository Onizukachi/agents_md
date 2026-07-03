# Оптимизация генерации купонов промо-кампаний

## 1. Бизнес контекст для задачи

- Генерация больших промо-кампаний с количеством купонов от `10_000` до `200_000` одной Sidekiq-джобой работала слишком долго и могла зависать или падать.
- Нужно было сохранить простой операционный сценарий для админки:
  - запуск генерации;
  - письмо по итоговому успеху/падению;
  - возможность запустить генерацию повторно после изменения `coupons_count`;
  - отсутствие ручной синхронизации между батчами.
- Уже созданные купоны при частичных ошибках должны сохраняться, чтобы следующая операция могла догенерировать только нехватающее количество.

## 2. Ключевые решения и обоснования

- Генерация разбита на батчи, а не на `1 job = 1 coupon`.
  Это даёт параллельность без лишней нагрузки на Sidekiq/Redis и без частой синхронизации.
- Основной [CouponGeneratorWorker](/Users/hikaru/projects/work/leveltravel/app/workers/promo_campaigns/coupon_generator_worker.rb) оставлен coordinator-воркером.
  Он считает дельту, фиксирует snapshot в `PromoCampaignOperation.metadata` и ставит batch jobs через `Sidekiq::Client.push_bulk`.
- Добавлен отдельный [CouponGenerationBatchWorker](/Users/hikaru/projects/work/leveltravel/app/workers/promo_campaigns/coupon_generation_batch_worker.rb).
  Он создаёт купоны в транзакции и обновляет прогресс операции.
- Каждая новая операция работает только с дельтой:
  `remaining_coupons_count = target_coupons_count - existing_coupons_count`.
  Это поддерживает:
  - повторный запуск после частичного падения;
  - повторный запуск после увеличения `coupons_count`.
- Если `remaining_coupons_count <= 0`, операция завершается как `success` без батчей и без письма.
  Это выбранный `no-op` сценарий.
- Синхронизация батчей организована только через `PromoCampaignOperation.metadata`.
  Не используются Redis-счётчики, Sidekiq Batch и отдельные служебные таблицы.
- Для `coupons.pin` введён уникальный индекс на уровне БД.
  Без этого параллельная генерация оставалась бы гонкой.
- В [CouponCreator](/Users/hikaru/projects/work/leveltravel/app/services/promo_campaigns/coupon_creator.rb) убран `Coupon.exists?` из hot path.
  Вместо этого используется retry на `ActiveRecord::RecordNotUnique`.
- Очередь генерации повышена с `low` до `normal`.
  `high` сознательно не использовался.
- Отдельная ветка `Rails.env.test?` в coordinator-воркере убрана.
  В тестах coordinator теперь мокает `push_bulk`, а выполнение и финализация проверяются отдельно на batch worker.

## 3. Структурированный список задач

- [x] Шаг 1: Зафиксировать формат `PromoCampaignOperation.metadata` для coordinator/batch-сценария и поля для `no-op`, прогресса и финализации.
- [x] Шаг 2: Добавить миграцию на уникальный индекс `coupons.pin`.
- [x] Шаг 3: Обновить генерацию `pin`, чтобы она переживала `RecordNotUnique` при параллельной вставке.
- [x] Шаг 4: Переписать `PromoCampaigns::CouponGeneratorWorker` в coordinator-режим.
- [x] Шаг 5: Добавить `PromoCampaigns::CouponGenerationBatchWorker`.
- [x] Шаг 6: Реализовать финализацию операции и обработку exhausted retries у batch jobs.
- [x] Шаг 7: Обновить `PromoCampaignOperation` методами подготовки snapshot и учёта batch progress.
- [x] Шаг 8: Обновить RSpec-покрытие для coordinator, `no-op`, частичных падений, дельты и retry по `pin`.
- [x] Шаг 9: Прогнать релевантные тесты.
- [x] Шаг 10: Синхронизировать `.agents` в `../agents_md`.

## 4. Как организована работа с metadata

### Ключи metadata

- `generated_coupons_count`
- `target_coupons_count`
- `existing_coupons_count`
- `remaining_coupons_count`
- `batch_size`
- `total_batches_count`
- `completed_batches_count`
- `failed_batches_count`

### Когда metadata заполняется

- На старте coordinator вызывает `PromoCampaignOperation#prepare_generation!`.
- В этот момент фиксируется snapshot операции:
  - сколько купонов нужно по текущему `promo_campaign.coupons_count`;
  - сколько купонов уже существует;
  - сколько реально нужно догенерировать;
  - сколько будет батчей;
  - какой размер батча используется.

### Как coordinator использует metadata

- Coordinator один раз считает:
  - `target_coupons_count`
  - `existing_coupons_count`
  - `remaining_coupons_count`
- После этого он больше не пересчитывает прогресс по базе и не меняет логику в зависимости от дальнейших изменений `promo_campaign`.
- Если `remaining_coupons_count <= 0`, операция сразу переводится в `success`, `finished_at` проставляется, батчи не ставятся.
- Если `remaining_coupons_count > 0`, coordinator раскладывает batch jobs и оставляет операцию в `processing`.

### Как batch jobs обновляют metadata

- Каждый batch worker создаёт ровно свой объём купонов внутри одной транзакции.
- После успешного коммита батч вызывает `complete_generation_batch!(generated_coupons_count: coupons_count)`.
- Внутри `PromoCampaignOperation` под `with_lock` обновляются:
  - `generated_coupons_count += coupons_count`
  - `completed_batches_count += 1`
  - `remaining_coupons_count -= coupons_count`

### Как обрабатываются падения batch jobs

- Пока у batch job есть retry, операция остаётся `processing`.
- Когда retry исчерпаны, `sidekiq_retries_exhausted` вызывает `fail_generation_batch!(error_message: ...)`.
- Внутри `PromoCampaignOperation` под `with_lock` обновляются:
  - `failed_batches_count += 1`
  - `error_message` сохраняется как последняя фатальная ошибка операции

### Как определяется финальный статус

- После каждого successful/failed batch считается:
  `processed_batches_count = completed_batches_count + failed_batches_count`
- Если `processed_batches_count < total_batches_count`, операция остаётся `processing`.
- Если обработаны все батчи:
  - `failed_batches_count == 0` -> `status = success`
  - `failed_batches_count > 0` -> `status = failed`
- В этот момент проставляется `finished_at`.

### Почему не хранится массив failed batches

- Пользователь согласовал упрощённую схему без массива ошибок по батчам.
- Для повторного запуска достаточно знать:
  - итоговый `status`;
  - сколько уже создано;
  - сколько осталось;
  - последнюю фатальную ошибку в `error_message`.
- Это упрощает JSON, снижает вероятность гонок и не требует отдельной истории по каждому батчу.

## 5. Текущее состояние проекта и уже выполненная работа

- Добавлен [CouponGenerationBatchWorker](/Users/hikaru/projects/work/leveltravel/app/workers/promo_campaigns/coupon_generation_batch_worker.rb).
- Переписан [CouponGeneratorWorker](/Users/hikaru/projects/work/leveltravel/app/workers/promo_campaigns/coupon_generator_worker.rb) под coordinator-сценарий.
- Восстановлена и расширена модель [PromoCampaignOperation](/Users/hikaru/projects/work/leveltravel/app/models/promo_campaign_operation.rb) под batch progress и финализацию.
- Обновлён [CouponCreator](/Users/hikaru/projects/work/leveltravel/app/services/promo_campaigns/coupon_creator.rb) для retry на конфликте `pin`.
- Добавлена миграция [20260703090736_add_unique_index_to_coupons_pin.rb](/Users/hikaru/projects/work/leveltravel/db/migrate/20260703090736_add_unique_index_to_coupons_pin.rb).
- `db/schema.rb` приведён к минимальному diff:
  - новая версия схемы;
  - `unique: true` на `index_coupons_on_pin`.
- Локально дубли `pin` были удалены вручную перед `db:migrate`.
- `db:test:load` успешно выполнен после ручной зачистки `schema.rb` от автогенерированного шума.

## 6. Проверки

Выполнялись:

```bash
docker exec lt.rails sh -lc 'cd /app && bundle exec rails db:migrate'
docker exec lt.rails sh -lc 'cd /app && bundle exec rails db:test:load'
docker exec lt.rails sh -lc 'cd /app && bundle exec rspec spec/workers/promo_campaigns/coupon_generator_worker_spec.rb spec/workers/promo_campaigns/coupon_generation_batch_worker_spec.rb spec/services/promo_campaigns/coupon_creator_spec.rb'
```

Последний целевой прогон после отказа от отдельной `Rails.env.test?` ветки:

```bash
docker exec lt.rails sh -lc 'cd /app && bundle exec rspec spec/workers/promo_campaigns/coupon_generator_worker_spec.rb spec/workers/promo_campaigns/coupon_generation_batch_worker_spec.rb spec/services/promo_campaigns/coupon_creator_spec.rb'
```

Результат: `8 examples, 0 failures`.

## 7. Критически важные принятые решения

- Не использовать `1 job = 1 coupon`.
- Использовать `batch_size = 500`.
- Не хранить массив `failed_batches` в `metadata`.
- `no-op` операция завершается как `success` и не отправляет письмо.
- Следующая операция всегда считает дельту заново по текущему факту в базе.
- Coordinator не исполняет батчи inline в `test`; вместо этого в спеках мокается `push_bulk`.

## 8. Точка продолжения, если сессия прервётся

- Основная реализация завершена.
- Если потребуется продолжение, ближайшие возможные шаги:
  1. прогнать более широкий набор тестов вокруг промо-кампаний и купонов;
  2. при необходимости показать прогресс операции в админке более явно через новые поля `metadata`;
  3. при необходимости добавить отдельное логирование постановки batch jobs.
