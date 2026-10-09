# Orders, Payments, and Receipts flow

This section describes the end-to-end flow of order creation, payment processing, and receipt generation.

## 1. Order prebuild (draft state)

During order formation (traveler details input, coupon application, price recalculation), the frontend sends incremental updates to:

- `Papi::V3::OrdersController#prebuild`

Characteristics:
- The order is not persisted yet.
- The endpoint is used for validation, pricing, and preview purposes.
- Multiple requests may be sent as the user modifies order data.
- No payment objects are created at this stage.

---

## 2. Order creation

When the user selects a payment method and confirms the purchase, the frontend sends a request to:

- `Papi::V3::OrdersController#create`

Characteristics:
- The order is persisted in the database.
- The order transitions from a draft/prebuild state to a created state.
- Further payment actions depend on the selected payment method.

---

## 3. Payment initiation

Available payment methods are determined by:

- `Order#payment_methods`

Based on the selected payment method, the frontend performs one of the following actions:

- **Card payment**:
  - Sends a request to:
    - `Papi::V3::PaymentsController#pay_card`

- **Non-card / redirect-based payment methods**:
  - Sends a request to:
    - `Papi::V3::PaymentsController#payment_params`
  - The response typically contains a payment URL to which the user must be redirected.

---

## 4. Payment creation and processors

Payments are created via:

- `PaymentBuilder`

Responsibilities of `PaymentBuilder`:
- Creates a `Payment` record.
- Assigns a `processor` to the payment.

The `processor`:
- Is a string representing a Ruby constant name.
- Points to a class responsible for interacting with a specific payment gateway API.
- All payment processors are located in:
  - `app/apis/payment_processor/`

Each processor encapsulates:
- API request building
- Authentication
- Gateway-specific logic

---

## 5. Asynchronous payment callbacks

Most payment gateways operate asynchronously.

After payment actions (authorization, unfreeze, capture, refund), external providers send callbacks (webhooks) to the system.

Callback handling:
- Implemented in classes with the `_callback_processor` suffix.
- Located in `app/apis/`
- Example:
  - `app/apis/alfa_pay_callback_processor.rb`

Responsibilities of callback processors:
- Validate incoming notifications.
- Update payment and order states.
- Trigger post-payment logic when applicable.

---

## 6. Receipts and line items generation

After successful payments or refunds:

- Receipts are generated.
- Line items are created and attached to receipts.

Domain models:
- `Receipt` — represents a fiscal receipt.
- `LineItemV2` — represents individual product or service items within a receipt.

Receipt generation logic:
- Implemented in:
  - `Receipts::Builder`

Responsibilities of `Receipts::Builder`:
- Create receipts for payments and refunds.
- Generate corresponding `LineItemV2` records.
- Ensure consistency between payments, receipts, and line items.

### 6.1 Advanced architecture: entry points and scenarios

Orders with `order.data[:agent_receipts]` branch off `Receipt.process_*_advanced_receipts` into the agent receipts flow (section 7); the scenarios below describe the old flow.

- **Auto detalization after trip**:
  `Order#mark_got_back` -> `Order#create_receipts`
  -> `Receipt.process_purchase_advanced_receipts(order, receipt_price, 'detailed')`
  -> `Receipts::Builder#create`
  -> `LineItemsV2::Advanced::Builder#build_detailed_line_items`.
- **Detailed refund after detalization**:
  `Payment#refund_detailed!` -> `Payment#mark_refunded!(..., params)` -> `Payment#create_advanced_receipts`
  -> `Receipt.process_refund_advanced_receipts(payment, amount, 'detailed', params)`
  -> `Receipts::Builder#create`
  -> `LineItemsV2::Advanced::Builder#build_refund_line_items`.
- **Manual fiscalization**:
  `Admin::ManualFiscalizationController#fiscalize_receipts`
  -> `LineItemsV2::Advanced::Builder.create_manual`.

### 6.2 Manager UI payment flow (`Manager::PaymentsController`)

- **Unfreeze payment** (`payment.frozen_amount` present):
  `Manager::PaymentsController#complete` with `action_type == 'release'`.
- **Capture payment** (`payment.frozen_amount` present):
  `Manager::PaymentsController#complete` with `action_type == 'capture'`.
- After capture:
  - **advanced refund** (before detalization):
    `Manager::PaymentsController#refund_advanced` with
    `action_type == 'refund'` and `type == 'advanced'`.
  - **detailed refund** (after detalization):
    `Manager::PaymentsController#refund_advanced` with
    `action_type == 'refund'` and `type == 'detailed'`.
- Detailed refund payload (example):
  `"refund_extras"=>{"669075"=>"12619.09", "669076"=>"12619.09"}, "refund_licence_amount"=>"10124.82", "refund_tour_amount"=>"380000"`.

## 7. Agent receipts flow (LT-54329, Akademia Servisa)

Status: implemented on `hotfix/LT-54329-akademia-agent-receipts-dev`, not yet in `develop` (check before relying on it). Full decisions: `.agents/tasks/54329/SPEC.md`.

Why it exists: Akademia Servisa (`Organization::AK`) sells as an agent. Advance receipts must carry the agent block (commission agent, supplier name, INN, phone), and before detalization the advances are moved to the suppliers of the detailed positions by counter-provision receipts.

The old flow (section 6) and the new one live side by side: old orders stay on the old flow until they age out (about the end of 2027). Never migrate old orders' advances.

### 7.1 Marker and scope

- Marker: `order.data[:agent_receipts] == true`, set once in `Order#set_agent_receipts_flag` (`before_create`) when `Receipts::AgentFlow.eligible?` holds: organization AK, not a certificate order, not a subagent order, partner does not skip fiscalization, created at or after `Receipts::AgentFlow::STARTS_AT` (a constant set after the release). Read it with `Receipts::AgentFlow.enabled?(order)`; never derive it from dates.
- Out of scope: LT/LP orders, certificate orders, manual tools (`ManualFiscalization`, `CreateRevert`).

### 7.2 Entry points

The fork is in `Receipt.process_purchase_advanced_receipts` and `Receipt.process_refund_advanced_receipts` (`Receipt::AdvancedMethods`): flagged orders go to `Receipts::AgentFlow.process_purchase` / `.process_refund`, everything else to `Receipts::Builder` as before. Code lives in `app/services/receipts/agent_flow/`; the Uniteller processor, router, parser, PDF, and price calculator are shared with the old flow.

### 7.3 Advance and the supplier snapshot

- Advance and every surcharge are one line for the tour supplier with the agent block; they are not split into tour, extras, and our services at payment time. Extras and our services reach their own suppliers only through transfers at detalization.
- `Snapshot` (`order.data[:agent_receipts_supplier]`) pins the agent (`Agent` = supplier organization + hotel owner) at the first advance receipt, once, under `Order.lock`. All advances and advance refunds go to that agent even if the supplier changes later. The hotel owner is included only when the LT-52232 rule applies (`FiscalProcessor::AgentSupplier`); for flagged orders the `HOTEL_OWNER_RECEIPTS_SINCE` cutoff is not checked. The agent of the order line is stored in `receipts.info_data[:hotel_organization_id]` at creation and is not recomputed on send.
- Without supplier INN or phone the receipt goes out without the agent block. Russian phones are normalized to `+7XXXXXXXXXX`.
- VAT as before: only on extras under USN with a supplier rate; advances use calculated rates (22 -> 122); the PDF signs them "22/122" via `Receipts::VatSummary`.

### 7.4 Detalization

`Receipts::AgentFlow::Detailing.call(order)` runs in one transaction under `Order.lock`:
1. If a detalization is already active, a storno of it (`StornoBuilder`, refund type 4).
2. `Plan` (pure logic, no DB) compares advance balances per agent with the detailed positions and builds transfers, taking the surplus from the last payment first; the donor is always the snapshot agent. Each transfer is a pair: advance refund plus advance purchase, both `advanced` receipts with `is_technical = true`, sent to Uniteller as type 15 (counter provision).
3. The detalization receipt itself.
4. Fiscalization is handed to `ReceiptChainWorker` after commit.

Only one detalization is active at a time. A surcharge after detalization puts the order on the manual review screen (`advance_after_detailing`); "repeat detalization" storno-es the active one and rebuilds it for the full amount. A repeat without new money does nothing.

When the plan cannot be built it creates no receipts and opens a `ReceiptDetailingBlock` with a reason: `frozen_payments`, `unfinished_advances`, `amount_mismatch`, `surplus_outside_snapshot`, `positions_mismatch`, `chain_failed`, `advance_after_detailing`. One open block per order and reason.

### 7.5 Fiscalization chain

Technical receipts, detalizations, and detailed refunds go to Uniteller strictly in id order (`Chain`): the next receipt is sent only after the previous one is fiscalized, already fiscalized ones are skipped. There is no stored plan; the pending receipts are the plan. One worker per order via a Redis lock (`receipts:agent_flow:chain:<order_id>`). `ReceiptChainWorker` retries 5 times over about 12 hours; after the last retry the order gets a `chain_failed` block. Receipts with `fiscalization_skipped = true` (the "without fiscalization" checkbox) are not sent.

### 7.6 Refunds

- Before detalization: a regular advance refund from the snapshot (`AdvanceBuilder`).
- After detalization: `DetailedRefund` takes suppliers and the hotel owner from the active detalization and is sent by the OrderID of the detalization receipt (`...-d`), because transfers zero the payment's order balance in Uniteller (`FiscalProcessor::Base#refund_by_detailing_order_id?`). A detailed refund during an unfinished chain goes last.

### 7.7 Visibility

Technical receipts (`receipts.is_technical`) and past detalizations with their storno are hidden from the client area (`Order#collect_receipts_urls` shows only the active detalization); a receipt-wait-group email made only of technical receipts is not sent. Their PDFs still render for the admin. The parser and PDF show type 15 as "ВСТРЕЧНОЕ ПРЕДОСТАВЛЕНИЕ".

### 7.8 Admin

- "Инструменты чеков" (role `admin_receipt_tools`) has a new-flow block: status, preview (the service in a rolled-back transaction plus receipt cards with the Uniteller parameters), "Детализировать" (only when no detalization exists), and the "без фискализации" checkbox.
- "Ручной разбор детализаций" (Система) lists open blocks with "repeat detalization".
- Receipts list: `is_technical` and `fiscalization_skipped` columns and filters; manual "fiscalize" on a chain receipt sends the whole chain in order.
