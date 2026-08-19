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
