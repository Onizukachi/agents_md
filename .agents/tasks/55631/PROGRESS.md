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

## Review fixes (2026-11-10)

- The guard moved from `PaymentController#init` into the `get_payment_and_order` before_action: it also covers `session_id`, `validate` and `create_invoice` and runs before `@payment.update(is_outer:)`.
- Site `orders#pay` and `orders#pay_remaining` redirect to the order page for a subagent order before touching or building a payment.
- PAPI `uniteller#pay` checks both the found payment's order and `params[:order_id]` before `PaymentBuilder`.
- `Payment#payment_url` returns `nil` (Ember turns `false` into the string "false"); the manager template `_payment.hjs` hides the copy link without a URL.

## Kept after review (reviewer-confirmed)

- PAPI `pay_3ds`/`data_3ds`/`acs_data`/`uniteller/pay_3ds` stay unguarded: they continue a 3DS flow that needs a bank registration from `pay_card`/`uniteller#pay`, both blocked now.
- `PaymentController#pay_card_uniteller` has no route; no guard.
- LT gift certificates on subagent orders (`ChargeOrderAmount` uses `update_attribute`): zero certificate payments ever on these partners' orders in production; documented residual.
- Manager cash/fine/debtor payments on subagent orders are blocked too, as agreed ("менеджерка" is one of the blocked entry points).
- `Order::AssignPartnerData` could attach a subagent partner via aflt to a site order, making it unpayable: no such order since 2025-11-01 in production; verification gap.
- The per-entry-point guards are a deliberate tradeoff: entry points share no payment-reuse layer, creation is centralized in the model validation.

## Rejected / changed (after the review gate)

- By the author's decision (2026-11-10) the guards in the legacy entry points were rolled back, with their specs: `papi/v3/uniteller_controller.rb`, `orders_controller.rb` (`pay`, `pay_remaining`), `payment_controller.rb`, `paylate/payment/create.rb`. Production logs: `uniteller/pay` 12 calls in 30 days (old iOS versions and tests), site `orders#pay` 1, `pay_remaining` 0, `payment#init`/`session_id`/`validate`/`create_invoice` 0 in 90 days, `payment/pay_card` link 1 in 90 days.
- Consequences: creating a new payment on a subagent order is still blocked by the model validation, but reuse of the webhook payment №1 through legacy `uniteller/pay`, `orders#pay`, `payment#init` stays open; `orders#pay_remaining` answers 500 for a subagent order (no template for `render(status: 422)`); `Paylate::Payment::Create` returns success with an unsaved payment. The `/payment/pay_card` link still redirects to `/transaction`, where PAPI refuses with `payment_forbidden`.
- The final head was not re-reviewed (the diff is a subset of the reviewed one).

## State

Related specs green (1105 examples). Committed on `feature/LT-55631-forbid-subagent-own-payments`; review gate in progress.
