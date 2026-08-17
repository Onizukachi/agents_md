# Currency analysis

## Index and windows

- Profile: `integrations`.
- Index pattern: `fbyc-currency-*`.
- Current window: `now-3h` to `now` unless the user specifies another one.
- Control window: the same three-hour interval shifted six days into the past. Build absolute timestamps when possible so the comparison is exact.

Before counting, verify that the selected index has fresh documents. Use concrete current backing indices if the alias does not work.

## Event families

### Rate requests served by currency

These are gRPC completion records:

- identify with `json.grpc.method = GetRate`;
- success: `json.grpc.code = OK`;
- failure: any other `json.grpc.code`, or an error-level GetRate record without a code.

Report total calls, successful calls, failed calls, codes, and the latest failure. These records normally do not contain a supplier. Report them as service-level errors unless a supplier field is explicitly present.

### Pulling rates from suppliers

Use structured log messages:

- success: `json.msg = pulled rates successfully` and related successful completion messages;
- failure: `json.msg = pulling rates failed` or `json.msg = failed to pull rates`;
- request-level evidence: `json.msg = performed request`, with `json.status_code`, `json.method`, and sanitized `json.url`.

Extract the supplier and reason from `json.error` when it contains `failed to pull rates from PROVIDER: REASON`. If the message is `context deadline exceeded` without a provider, report it as a pulling-level failure and do not invent a provider.

## New-error comparison

For every current pulling failure, create a comparison key:

`PROVIDER | normalized reason`

Normalize only unstable details: trim whitespace, lowercase for comparison, remove timestamps, request IDs, query strings, tokens, and full URLs. Preserve meaningful HTTP status codes and semantic reasons such as `malformed response`, `401 unauthorized`, or `context deadline exceeded`.

Query the control window for the same failure event families and build its key set. Classify current failures as:

- known: key exists in the control window;
- new: key absent from the control window;
- unclassified: supplier or reason cannot be reliably extracted.

Known pulling failures do not alone make the service unhealthy. Any new or unclassified failure should be surfaced as a problem until the user confirms it is expected noise. Always surface `GetRate` failures regardless of the control window.

## Aggregations and samples

Start with these aggregations in the current and control windows:

- `json.grpc.method` and `json.grpc.code` for served rate requests;
- `json.msg` and `json.level` for event families;
- `json.error` for pulling failures;
- `json.status_code` for outbound request results;
- `kubernetes.pod.name` and `container.image.name` for concentration by deployment.

Fetch representative documents for each distinct failure key and at least one successful document per event family. Do not use only bucket counts to make the final assessment.

## Output shape

Use this compact structure:

```text
Итог: [currency работает | currency работает частично | есть проблемы в currency]
Период: [current window]; сравнение: тот же интервал 6 дней назад.

Получение rate из currency:
- всего / успешно / ошибок: ...
- проблемы: ...

Pulling rates:
- всего успешных событий / ошибок: ...
- известные ошибки: PROVIDER — причина — количество
- новые ошибки: PROVIDER — причина — количество, последнее событие

По поставщикам:
- PROVIDER: [норма | известная проблема | новая проблема]

Основание: [индекс, ключевые поля, ограничения данных].
```

If there are no GetRate failures and only known pulling failures, say explicitly that the service is operational but has known supplier-specific issues.

If every current pulling failure matches the control window, treat currency as working and omit those failures entirely from the report. Show only new or unclassified pulling failures.

