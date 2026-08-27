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
A legal entity within the LevelTravel business (e.g. the entities referred to internally as LT, LP, AK); orders, payments, and receipts are attributed to one.
_Avoid_: Operator, Company

**Operator**:
An external tour operator/wholesaler that supplies hotel and tour inventory to the product.
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
The "Сверка Партнёры" Registry File format filed under partner_id 6 alongside the separate Getblogger format; each row lists a different real partner for context, but every resulting Partner Operation is still attributed to partner 6, like the rest of that Registry File.
_Avoid_: Multi-partner file, Getblogger file

**Alfa Miles Report**:
An outbound registry LevelTravel generates daily, listing Alfa-Bank miles purchase/return operations (from PartnerBonus status transitions) for Alfa-Bank's own reconciliation - the reverse direction from a Registry File, which arrives from a partner rather than being produced for one.
_Avoid_: Registry File, реестр (without qualifier)
