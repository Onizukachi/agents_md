# Searcher analysis

## Index and windows

- Profile: `integrations`.
- Index pattern: `fbyc-searcher-*`.
- Current window: `now-3h` to `now` unless the user specifies another one.
- Control window: the same interval shifted six days into the past.

Verify freshness. If the datastream pattern does not return current documents, select the current concrete backing index from `list_indices`.

## Search statistics

Use only records with `json.event = search_job` for supplier search health. The supplier name is `json.operator_name`; the status is `json.status`. Relevant statuses include:

- `success` — successful supplier search;
- `failed` — failed supplier search;
- `timeout` — supplier search timeout;
- `all_filtered` — search returned tours but all were filtered out;
- `no_results` — no results, not itself an error;
- `skipped` — skipped by an intentional rule, not itself an error.

Calculate for the current and control windows, overall and per `json.operator_name`:

- total `search_job` events;
- count and share of `failed`;
- count and share of `timeout`;
- count and share of `all_filtered`;
- counts of `success`, `no_results`, `skipped`, and other statuses for context.

Do not use lifecycle records such as `pending`, `performing`, or `completed` as supplier outcome statistics when `search_job` records are available. Do not double-count other event types or HTTP access logs.

## Alert rule

For each supplier and each suspicious status (`failed`, `timeout`, `all_filtered`), compare current count and current share with the same metric in the control window.

Classify as a problem only when both conditions hold:

1. current absolute count is more than 2× the control count; and
2. current share of that status is more than 2× the control share.

Additionally, for `failed` and `timeout`, the current status share must be at least 20% of all `search_job` attempts for that supplier. A supplier below 20% is not a reported search problem, even if the status grew more than 2× versus control; retain the event only as internal context.

If the control value is zero, a single current event is an isolated error and does not trigger a problem. A repeated current event with no historical baseline is a new signal and should be reported as suspicious; do not claim a confirmed 2× increase when the baseline is zero.

Ignore one isolated event for a supplier/status in the current window, but still show it in the detail. This exception does not apply to panic events.

For `failed` and `timeout`, treat an alert as a direct search reliability problem. For `all_filtered`, treat an alert as suspicious degradation and explain that it may indicate changed supplier responses, filtering, or mapping; do not claim a root cause without supporting logs.

## Drill-down

When a supplier/status is suspicious:

- fetch representative `search_job` documents with `json.reason`, `json.searcher_status`, durations, and tour counters;
- aggregate by `json.reason` and `json.searcher_status`;
- inspect `json.msg` and related events such as `searcher_perform_supplier_search_failed`, `supplier_search_started`, and `supplier_search_finished`;
- check concentration by `kubernetes.pod.name` and `container.image.name`;
- report the latest event time and safe reason, omitting request IDs and encoded payloads.

## Panic

Apply the common panic check to the searcher index. Search case-insensitively in `message`, `json.msg`, `json.error`, and `json.stacktrace` for `panic`, `panic:`, `panic(`, or `runtime error`. Any panic is a problem, even if it is a single event. Deduplicate paired records by `request_id` when available.

## Output

Use this structure:

```text
Итог: [searcher работает | searcher работает частично | есть проблемы в searcher]
Период: [current window]; контроль: то же окно 6 дней назад.

По поставщикам:
- PROVIDER: failed [count/share vs control], timeout [count/share vs control], all_filtered [count/share vs control], статус.

Подозрительные изменения:
- PROVIDER / STATUS: [рост >2× по количеству и доле | единичное событие | новый сигнал без baseline], причина.

Panic: [count, или не найдено]
Основание: [индекс, поля, ограничения и примеры причин].
```

Call `searcher` healthy only when no supplier has an alert under the two-part rule and no panic is found. If only isolated events or `all_filtered` changes without both 2× conditions exist, report them as observations rather than failures.

Keep the report compact: list only suppliers with a confirmed failed/timeout alert, including `N ошибок / M успешных, всего K попыток (P% ошибок)`. Do not mention `all_filtered` when it does not meet the 2× alert rule, and do not describe normal suppliers.

When there are no confirmed alerts, write only `searcher работает` without explaining the 20% threshold or listing observed low-volume errors.

