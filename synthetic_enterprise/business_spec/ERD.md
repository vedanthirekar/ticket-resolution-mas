# Luma Wellness Entity Relationship Diagram

Status: Draft for Gate B schema review

The diagrams emphasize ownership and evidence flow. UUID primary keys and ordinary
timestamp columns are omitted from boxes for readability.

## Organization, appointments, and billing

```mermaid
erDiagram
    LOCATION ||--o{ LOCATION_HOURS : has
    LOCATION ||--o{ EMPLOYEE_LOCATION : assigns
    EMPLOYEE ||--o{ EMPLOYEE_LOCATION : works_at
    LOCATION ||--o{ LOCATION_SERVICE : offers
    SERVICE ||--o{ LOCATION_SERVICE : offered_at
    EMPLOYEE ||--o{ EMPLOYEE_SERVICE : qualified_for
    SERVICE ||--o{ EMPLOYEE_SERVICE : performed_by
    EMPLOYEE ||--o{ EMPLOYEE_SCHEDULE : scheduled
    LOCATION ||--o{ EMPLOYEE_SCHEDULE : hosts

    CUSTOMER ||--o{ APPOINTMENT : books
    LOCATION ||--o{ APPOINTMENT : hosts
    SERVICE ||--o{ APPOINTMENT : quotes
    EMPLOYEE ||--o{ APPOINTMENT : assigned
    APPOINTMENT o|--o| APPOINTMENT : replaces
    APPOINTMENT ||--o{ APPOINTMENT_EVENT : records

    CUSTOMER ||--o{ INVOICE : owes
    APPOINTMENT o|--o{ INVOICE : creates
    INVOICE ||--|{ INVOICE_ITEM : itemizes
    APPOINTMENT o|--o{ INVOICE_ITEM : concerns
    SERVICE o|--o{ INVOICE_ITEM : prices
    INVOICE ||--o{ PAYMENT : attempted_by
    CUSTOMER ||--o{ PAYMENT : submits
    PAYMENT ||--o{ PAYMENT_EVENT : records
    PAYMENT ||--o{ REFUND : returns

    LOCATION {
        uuid id PK
        string public_reference UK
        string timezone
    }
    APPOINTMENT {
        uuid id PK
        string public_reference UK
        timestamptz scheduled_start
        timestamptz scheduled_end
        string status
        int quoted_price_cents
    }
    APPOINTMENT_EVENT {
        uuid id PK
        string event_type
        string actor_type
        string initiating_party
        timestamptz occurred_at
    }
    PAYMENT {
        uuid id PK
        string obligation_reference
        string status
        int captured_amount_cents
        int refunded_amount_cents
    }
    REFUND {
        uuid id PK
        int amount_cents
        string status
        string idempotency_key UK
    }
```

## Memberships

```mermaid
erDiagram
    CUSTOMER ||--o{ MEMBERSHIP : enrolls
    MEMBERSHIP_PLAN ||--o{ MEMBERSHIP : governs
    MEMBERSHIP ||--o{ MEMBERSHIP_LEDGER : owns
    APPOINTMENT o|--o{ MEMBERSHIP_LEDGER : settles
    MEMBERSHIP_LEDGER o|--o{ MEMBERSHIP_LEDGER : reverses
    MEMBERSHIP_LEDGER ||--o{ CREDIT_ALLOCATION : consumed_entry
    MEMBERSHIP_LEDGER ||--o{ CREDIT_ALLOCATION : source_grant

    MEMBERSHIP {
        uuid id PK
        string public_reference UK
        string status
        string terms_policy_id
        int terms_version
    }
    MEMBERSHIP_LEDGER {
        uuid id PK
        string entry_type
        int credit_delta
        timestamptz effective_at
        timestamptz expires_at
    }
    CREDIT_ALLOCATION {
        uuid consumption_entry_id FK
        uuid grant_entry_id FK
        int quantity
    }
```

## Booking availability

```mermaid
erDiagram
    LOCATION ||--o{ LOCATION_SERVICE_SETTING : configures
    SERVICE ||--o{ LOCATION_SERVICE_SETTING : configures
    EMPLOYEE ||--o{ EMPLOYEE_BOOKING_SETTING : overrides
    SERVICE o|--o{ EMPLOYEE_BOOKING_SETTING : narrows
    LOCATION ||--o{ LOCATION_RESOURCE : owns
    LOCATION o|--o{ BOOKING_BLOCK : blocks
    EMPLOYEE o|--o{ BOOKING_BLOCK : blocks
    SERVICE o|--o{ BOOKING_BLOCK : blocks
    LOCATION_RESOURCE o|--o{ BOOKING_BLOCK : blocks
    CUSTOMER ||--o{ BOOKING_ATTEMPT : submits
    LOCATION ||--o{ BOOKING_ATTEMPT : requests
    SERVICE ||--o{ BOOKING_ATTEMPT : requests
    EMPLOYEE o|--o{ BOOKING_ATTEMPT : prefers
    BOOKING_ATTEMPT o|--o| APPOINTMENT : commits
```

## Policy knowledge

```mermaid
erDiagram
    POLICY_DOCUMENT ||--|{ POLICY_VERSION : versions
    POLICY_VERSION o|--o| POLICY_VERSION : supersedes
    POLICY_VERSION ||--|{ POLICY_SECTION : contains
    POLICY_SECTION o|--o{ POLICY_SECTION : parent_of
    POLICY_SECTION ||--o{ POLICY_SECTION_LINK : source
    POLICY_SECTION ||--o{ POLICY_SECTION_LINK : target

    POLICY_DOCUMENT {
        uuid id PK
        string policy_id UK
        string policy_area
    }
    POLICY_VERSION {
        uuid id PK
        int version
        date effective_from
        date effective_through
        jsonb scope
        string content_checksum UK
    }
    POLICY_SECTION {
        uuid id PK
        string section_id UK
        text body
        tsvector search_vector
    }
```

