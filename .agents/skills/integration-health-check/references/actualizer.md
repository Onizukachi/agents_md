# Actualizer analysis

## Index and windows

- Profile: `integrations`.
- Index pattern: `fbyc-actualizer-*`.
- Current window: `now-3h` to `now` unless the user specifies another one.
- Control window: the same interval shifted six days into the past.

Verify freshness and use a current concrete datastream backing index if the pattern does not return current documents.

## Actualization success

Use records with `json.msg = actualization_stat`. The supplier is `json.supplier_id`. Classify the record as:

- success when `json.error` is absent;
- failure when `json.error` is present.

Calculate total, success, failure, and failure share overall and by supplier. Include `json.duration`, `json.path`, `json.tour_id`, and a normalized safe error reason in drill-downs.

## Concretization success

Use records with `json.msg = concretization_stat` and apply the same success/failure rule based on `json.error`. Calculate the same overall and per-supplier metrics. Include price change fields and duration when explaining a failure, but do not expose request IDs or sensitive payloads.

Do not mix `actualization_stat`, `concretization_stat`, `package_actualization_stat`, `tour_actualization_stat`, or unrelated HTTP logs into one rate. Report the two metrics separately.

## Baseline and classification

Compare current and control windows overall and by `json.supplier_id`.

- Ignore one isolated failure in a metric/supplier for the current window; report it as an isolated error.
- Repeated failures are a problem signal only when the overall metric is materially below the good level of about 95% or the failure share materially worsens versus control. Rates around 95% with no material degradation are normal; treat routine supplier-level failures as noise.
- If the current failure share is more than 2× the control failure share, report a problem signal for that metric/supplier.
- If the control failure share is zero, report repeated current failures as a new signal without claiming a numeric 2× increase.
- A supplier with no current events is not automatically failed; distinguish no traffic from missing data.

Show counts and rates, not only percentages. Keep actualization and concretization conclusions separate because one can degrade while the other remains healthy.

## Error drill-down

For repeated or increased failures:

- aggregate normalized `json.error` by `json.supplier_id` and metric;
- fetch representative failed records and a successful record for comparison;
- inspect `json.path`, `json.duration`, pod, and image;
- deduplicate paired records by `request_id` when needed;
- redact URLs, tokens, IDs, and encoded payloads.

## Panic and service restart

Apply the common panic check to the actualizer index. Search case-insensitively in `message`, `json.msg`, `json.error`, and `json.stacktrace` for `panic`, `panic:`, `panic(`, or `runtime error`. Any panic is a problem, even one event.

Also search for service restart evidence in application and sync-logger records: startup/listening/initialization messages, shutdown/exit messages, restart markers, crash-loop or retry-exhaustion messages, and Kubernetes pod changes when metadata supports them. Any confirmed service restart is a problem even if actualization rates are currently good. Report time, pod/image, and safe restart reason. Do not infer a restart from a routine request or a normal worker task retry alone.

## Output

```text
Итог: [actualizer работает | actualizer работает частично | есть проблемы в actualizer]
Период: [current window]; контроль: то же окно 6 дней назад.

Actualization:
- всего / успешно / ошибок: ...
- по supplier_id: ...
- новые или повторяющиеся причины: ...

Concretization:
- всего / успешно / ошибок: ...
- по supplier_id: ...
- новые или повторяющиеся причины: ...

Panic: [count, или не найдено]
Restart: [count, или не найдено]
Основание: [индекс, поля, ограничения и объём выборки].
```

Call actualizer healthy when actualization and concretization are around 95% or higher, neither materially worsens versus control, and no non-exempt panic or confirmed restart is found. Mention only material deviations.

If actualization and concretization rates are good and do not materially worsen versus control, report `actualizer работает` and omit supplier-level routine errors. Ignore and do not report the known logger-sync panic text `panic: failed to sync logger`.

