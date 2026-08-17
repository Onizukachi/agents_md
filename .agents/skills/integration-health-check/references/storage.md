# Storage analysis

## Index and windows

- Profile: `integrations`.
- Index pattern: `fbyc-storage-*`.
- Current window: `now-3h` to `now` unless the user specifies another one.
- Control window: the same interval shifted six days into the past.

Verify freshness and use the current concrete datastream backing index when the pattern does not return current documents.

## gRPC metrics

Use completion records with `json.grpc.method` and `json.grpc.code`.

- Successful calls: `json.grpc.code = OK`.
- Failed calls: any non-`OK` code or a record with `json.error`.
- Latency: numeric `json.grpc.time_ms`, in milliseconds.
- Methods: report at least `ReadTours`, `WriteTours`, `ApplyRules`, `ViewCatalog`, and `GetStats`; include other methods when present.

The Grafana RPM panel counts successful (`grpc.code=OK`) calls, groups by `json.grpc.method`, and uses one-minute time buckets. Reproduce that definition when calculating RPM. Do not treat the Grafana red threshold of 80 as a health SLO; it is only a panel visualization setting.

The Grafana latency panel calculates `avg(json.grpc.time_ms)` by method. Its red threshold of 500 ms is also a visualization hint, not a confirmed business limit.

## Dynamic normal baseline

Treat the observed control-window averages as the normal baseline, separately for each method:

- baseline RPM = successful calls / number of minutes with the control window;
- baseline latency = average `json.grpc.time_ms` for the method in the control window;
- baseline error rate = failed calls / all gRPC completion calls.

Report current and baseline values side by side. Do not compare methods with different workloads as if they had one shared RPM or latency norm.

Use these practical deviation signals unless the user gives different thresholds:

- current successful RPM below 50% of the control baseline: suspicious throughput drop;
- current average latency above 2× the control baseline: suspicious latency increase;
- current error count greater than one: problem signal; compare count and error rate with the control window and highlight a more-than-2× increase;
- a single error is an isolated event and does not worsen the overall status;
- zero baseline requires caution: report the new event and sample size, but do not claim a numeric 2× increase.

These deviation signals are not substitutes for evidence. Fetch representative failed calls and inspect the method, gRPC code, safe error reason, pod, and image before concluding.

## Error and latency drill-down

For repeated or increased errors:

- aggregate `json.grpc.code`, `json.error`, `json.grpc.method`, `kubernetes.pod.name`, and `container.image.name`;
- fetch the latest failed records and one successful record for comparison;
- deduplicate paired records by `request_id` when the same call is logged more than once;
- redact request IDs, tokens, URLs, and encoded payloads in the response.

For latency anomalies, aggregate average, count, p95 when supported, and max `json.grpc.time_ms` by method. If only average is available, say so. A high average based on very few calls is an observation, not a confirmed outage.

## Panic

Apply the common panic check to the storage index. Search case-insensitively in `message`, `json.msg`, `json.error`, and `json.stacktrace` for `panic`, `panic:`, `panic(`, or `runtime error`. Any panic is a problem, even a single event.

## Output

```text
Итог: [storage работает | storage работает частично | есть проблемы в storage]
Период: [current window]; норма: средние значения того же окна 6 дней назад.

По методам:
- METHOD: RPM [current vs baseline], latency [current vs baseline], errors [current vs baseline], статус.

Проблемы и отклонения:
- [METHOD / code / reason / pod]: ...

Panic: [count, или не найдено]
Основание: [индекс, поля, объём выборки и ограничения].
```

Call storage healthy only when there are no panic events, no repeated/new errors, and no meaningful throughput or latency degradation against the dynamic baseline. Mention isolated errors separately without turning them into a service failure.

Keep the report to one line when RPM and latency are within the control baseline and there is no meaningful degradation: `storage работает, RPM и latency в норме`. Do not list routine baseline-level gRPC noise in that case.

