# Booker analysis

## Index and windows

- Profile: `integrations`.
- Index pattern: `fbyc-booker-*`.
- Current window: `now-3h` to `now` unless the user specifies another one.
- Control window: the same interval shifted six days into the past; use it for `UpdateBookingInfo Warning` growth and context, not to hide metric failures.

Verify freshness and use concrete datastream backing indices when the alias does not return data.

## Booking (`book`)

Use `json.msg = book_stat`, `json.event = book`, or path `/booker_api/v1/book`. Count `json.success=true` as success and `json.success=false` as failure. Do not use `upsert_booking` or `upsert_booking_stat` in this metric.

Calculate:

- overall booking rate = successful `book_stat` / all `book_stat` × 100;
- the same rate by `json.operator_name` and, when useful, `json.supplier_id`.

Overall rate above or equal to 90% is acceptable. Below 90% is a problem. Always report supplier-level rates and sample sizes even if the overall rate is acceptable. Use `json.error` and representative records to explain failures; redact secrets and long identifiers.

Do not classify a single failed `book_stat` as a provider or service problem when it is the only failure in the current window. Report it as an isolated error. Apply the 90% threshold when failures repeat or the failed count is greater than one. Thus a provider with `0/1` is not a problem by itself, while a provider with `0/125` is a problem.

## Prebook

Use `json.msg = prebook_stat` and group by `json.tour_id`. Calculate the success rate from `json.success` for every tour ID with enough observations to be meaningful; still show low-volume IDs separately without overclaiming.

- 90% or higher: good;
- 85% to less than 90%: tolerable, report as warning;
- below 85%: problem.

If a tour has only one failed prebook event, classify it as an isolated error rather than a problem; apply the percentage bands when failures repeat or the failed count is greater than one.

Report the overall prebook rate and the worst tour IDs with `success / total`, percentage, and last observed time.

## Update booking info synchronization

Use `json.msg = update_booking_stat`, `json.event = update_booking`, and path `/booker_api/v1/update_booking_info`. Calculate overall and per-`json.operator_name` success rates from `json.success`.

- 95% or higher: acceptable;
- below 95%: problem.

Ignore one isolated failed `update_booking_stat` for a supplier when it is the only failure in the current window. Continue to calculate and report the rate, but do not mark that supplier as problematic unless failures repeat or exceed one event.

Use `json.msg = error updating booking info` and `json.path = /booker_api/v1/update_booking_info` to enumerate causes and affected suppliers/orders when available. `request_completed` with `json.http_status >= 500` is additional failure evidence, but avoid double-counting it with the corresponding `update_booking_stat` record when computing the rate.

### UpdateBookingInfo Warning

Search case-insensitively for `UpdateBookingInfo Warning` in `json.msg`, `message`, and relevant warning fields. This warning is expected to exist. Count current and control-window events and group by supplier/operator and safe warning reason when fields exist.

Treat the warning volume as a problem signal only when the current count is more than twice the control-window count. If the control count is zero, report the current count as a new warning signal but distinguish it from a confirmed rate failure. Do not treat the mere presence of this warning as a failure.

## Booking info

Use `json.msg = booking_info_stat`, `json.event = booking_info`, or path `/booker_api/v1/booking_info`. Calculate overall and per-operator success rates from `json.success`.

- 99% or higher: normal;
- below 99%: problem.

Ignore one isolated failed `booking_info_stat` in the same way; repeated failures remain a problem.

Show the main `json.error` reasons and supplier/operator concentration. If there are no samples, report that the metric is not observable rather than declaring success.

## Panic check

Search the booker index for case-insensitive `panic`, `panic:`, `panic(`, or `runtime error` across `message`, `json.msg`, `json.error`, and `json.stacktrace`. Any match is a problem, including a single panic. Count unique events using `request_id` when available to avoid counting both an error log and its 500 response as separate panics.

## Output

Use this structure:

```text
Итог: [booker работает | booker работает частично | есть проблемы в booker]
Период: [current window]; контроль: то же окно 6 дней назад.

Book: [success / total = rate%]; по поставщикам: ...
Prebook: [overall rate%]; проблемные tour_id: ...; терпимые: ...
Update booking info: [success / total = rate%]; по поставщикам: ...
UpdateBookingInfo Warning: [current count] vs [control count], [норма | рост более чем в 2 раза]
Booking Info: [success / total = rate%]; по поставщикам: ...
Panic: [count, или не найдено]

Основание: [индекс, поля, ограничения и примеры причин].
```

Do not call `upsert_booking` a failure and do not include it in booking rates. A known supplier-specific booking error still contributes to the observed failure rate; do not silently ignore it unless the user explicitly adds a separate exception rule.

Keep the report compact. For every problematic supplier show attempts and percentage in the format `N ошибок / M попыток (P% от успешных статусов)`. Do not list normal suppliers or isolated errors unless needed for context.

Make the counts explicit: use `N ошибок / M успешных, всего K попыток (P% ошибок)`. Never use an ambiguous `N / M`. For each listed provider include the concrete failed operation (`Book`, `Prebook`, or `Update booking info`) and a short safe reason from `json.error`; if several reasons exist, show the dominant one with its count.

