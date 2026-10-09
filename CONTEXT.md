# LevelTravel

LevelTravel is a travel aggregator: it searches, books, and sells travel Packages sourced from external Operators - it does not operate tours itself.

## Language

**Client**:
The traveler who searches, books, and purchases through the product.
_Avoid_: User, Customer, Account

**User**:
An internal LevelTravel staff account (e.g. agent, manager) with system access.
_Avoid_: Client, Employee

**Organization**:
A legal entity within the LevelTravel business: Level Travel (LT), Level Putyeshestviya (LP), or Akademiya Servisa (AK). Orders, Payments, and Receipts are attributed to one; AK sells as an agent (see Agent Receipts Flow).
_Avoid_: Operator, Company

**Operator**:
An external tour operator/wholesaler (ТО in internal talk) that supplies hotel and tour inventory to the product.
_Avoid_: Organization, Provider, Supplier

**Package**:
A bookable bundle purchased by a Client - either a full tour (flight + hotel) or a hotel-only stay.
_Avoid_: Tour, Booking (except when quoting user-facing copy)

**Matcher**:
A component that reconciles LevelTravel's own records (hotels, meal plans, travelers) against the equivalent data supplied by an external Operator.
_Avoid_: Sync, Mapper, Integration

**Operator Organization**:
The legal entity of an external Operator that contracts with LevelTravel and is recorded as the supplier on a Package. An Operator may have several; one is marked as its main entity.
_Avoid_: Organization, Supplier, Legal entity

**Departure**:
The city a Package's flight leaves from, chosen by the Client at search time.
_Avoid_: Origin, From city, Departure country

**Registry File**:
A reconciliation file a partner uploads describing what LevelTravel owes or is owed on their orders, processed row-by-row into Partner Operations.
_Avoid_: Report, Upload

**Partner Operation**:
One row of a processed Registry File, recording an order, a cost, and (optionally) the Payment it reconciles against.
_Avoid_: Registry entry, Transaction

**Accounting Date**:
An administrative date entered by staff on a Registry File marking which accounting period it belongs to; it drives no processing logic and is distinct from a Partner Operation's own Repo Date.
_Avoid_: Reporting date, Period, Repo date

**Repo Date**:
The date of the underlying operation as reported in a partner's Registry File, stored per Partner Operation.
_Avoid_: Accounting date, Transaction date

**Order-Based Registry**:
A Registry File whose rows already carry the order's own ID and commission amount, so the matching order never needs to be looked up.
_Avoid_: Transaction-based registry (its opposite, not yet named in code)

**Universal Registry**:
The "Сверка Партнёры" Registry File format filed under one fixed Partner alongside the separate Getblogger format; each row lists a different real partner for context, but every resulting Partner Operation is still attributed to that one Partner, like the rest of that Registry File.
_Avoid_: Multi-partner file, Getblogger file

**Alfa Miles Report**:
An outbound registry LevelTravel generates daily, listing Alfa-Bank miles purchase/return operations (built from the status changes of Alfa-Bank miles bonuses) for Alfa-Bank's own reconciliation - the reverse direction from a Registry File, which arrives from a partner rather than being produced for one.
_Avoid_: Registry File, реестр (without qualifier)

**Whitelabel Partner**:
A Partner that runs the product on its own domain under its own brand, so Clients never see LevelTravel's name; distinct from an API partner, which only consumes the API.
_Avoid_: WL, Reseller, Affiliate

**Partner Document Override**:
A partner-specific version of a legal document that stands in for LevelTravel's base version for exactly one Partner; when none exists, the base document is used.
_Avoid_: Partner article, WL agreement, Custom agreement

**Order**:
A Client's purchase of a Package; Payments and Receipts attach to it.
_Avoid_: Booking

**Payment**:
A movement of the Client's money on an Order through a payment gateway: authorization, capture, and refund.
_Avoid_: Transaction

**Receipt**:
A fiscal receipt registered for a Payment or refund of an Order. It is either an Advance Receipt or a Receipt of a Detalization.
_Avoid_: Check, Invoice

**Advance Receipt**:
A Receipt issued when money arrives, before the Order is detalized; it registers the money as an advance for the Order, not as sold services.
_Avoid_: Prepayment receipt

**Detalization**:
Re-registering an Order's total as separate positions (tour, extras, our services), each attributed to the Receipt Agent that actually provides it, closing the advances; done after the trip or on demand.
_Avoid_: Itemization, Breakdown

**Receipt Agent**:
The legal entity whose service a Receipt line sells while the Organization acts as its commission agent: the Package's Operator Organization, or the Hotel Owner when the Order qualifies. Its name, INN, and phone print in the receipt's agent block.
_Avoid_: Supplier

**Hotel Owner**:
The legal entity that owns a hotel, taken from the state hotel registry; for dynamic hotels in Russia it replaces the Operator Organization as Receipt Agent when the Order qualifies.
_Avoid_: Hotel organization, Hotelier

**Agent Receipts Flow**:
The receipt scheme for Orders of Akademiya Servisa (AK): advances are registered on one Receipt Agent fixed at the Order's first advance, and before Detalization they are moved to the Receipt Agents of the detalized positions by Technical Receipts. Orders created before the flow started stay on the old scheme.
_Avoid_: New flow

**Technical Receipt**:
A Receipt that only re-attributes money between Receipt Agents (an advance transfer in counter-provision form, or the reversal of an earlier Detalization); it goes to the fiscal operator but is never shown to the Client.
_Avoid_: Transfer receipt, Hidden receipt

**Detalization Block**:
An Order whose Detalization cannot be done automatically (for example the amounts do not add up or a Payment is frozen) and waits for manual review.
_Avoid_: Failed detalization
