# LT-55631 Progress

No SPEC.md: the scope was agreed in the conversation on 2026-11-10.

## Scope agreed

- Subagent = `Order#subagent?` (`partner.is_outer_first_line`). `Partner#subagent?` (excludes CRPO 1044/1193) is not used.
- A subagent order is paid only by the partner webhooks `POST /papi/v3/orders/:id/notify` and `POST /papi/v3/orders/:id/payments`.
- No surcharges through our payment methods either, including the surcharge link after a package replacement.
- `payments/payment_methods` stays as is (the user rejected hiding the methods there).

## Production findings (Replica, 2025-11-01..2026-11-10)

- Webhook payments: Ozon/CRPO_PP/arlekinotour/VTB via `/notify` (payment №1 named after the partner, processor `Uniteller`/`TBank` without rrn/card), TravelSolutions via `/payments` (`ExternalProcessor`).
- Real payments outside the webhook: 2, both TravelSolutions surcharges after a manager package replacement (orders 371139949, 376393039), paid on the order page through `POST /papi/v3/payments/pay_card`. The deposit was also charged for the same amount on capture.

## Done

- `Payment` validation on create `subagent_order_paid_by_webhook`: a subagent order accepts only webhook payments (`Payment#partner_webhook?`: `ExternalProcessor` or `referer_type: partner_app`). This closes every `PaymentBuilder` caller, including manager-created payments and Paylate.
- Explicit refusals before reusing an existing payment by number or opening a payment form: PAPI `payments/pay_card`, `payments/payment_params`, `orders/pay`, `uniteller/pay`; site `orders#pay`, `payment#init`; `Paylate::Payment::Create`.
- Surcharge link: `Payment#payment_url` returns `false`, `payment#pay_card` returns 404 for a subagent order.
- New PAPI error code `payment_forbidden` ("Оплата этого заказа недоступна"); documented in `docs/papi/v3/controllers/payments/3.0.yml` (`pay_card`, `payment_params`) and `orders/3.0.yml` (`pay`).
- Specs: new examples for the validation, `payment_url`, the PAPI entry points and the link; specs that paid subagent orders through our acquiring now use the `:partner_webhook` payment trait.

## Rejected / changed

- Hiding payment methods in `payments/payment_methods`: rejected by the user, the refusal happens when a payment is attempted.

## State

Focused specs green (1002 examples across subagent/payment specs). Not committed.
