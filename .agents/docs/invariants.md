# Project Invariants

## Dependencies

- Do not add gems without explicit user approval.
- When proposing a gem, first give a short rationale and tradeoffs.

## External HTTP

- Use `ExternalRequest` as the wrapper around `Typhoeus`.
- Do not introduce `Faraday` or `RestClient`.

## Feature flags

- Treat `use_advanced_receipts` and `new_payments_architecture` as always `true`.
- These flags are legacy; do not implement or rely on their `false` behavior.
