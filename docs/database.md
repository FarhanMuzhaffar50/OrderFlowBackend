# Database design

PostgreSQL is the system of record. Monetary values are integer minor units (`*_amount_minor`, `unit_price_minor`) so arithmetic is exact and currency rounding is explicit at the boundary.

```mermaid
erDiagram
  USERS ||--o{ CARTS : owns
  CARTS ||--o{ CART_ITEMS : contains
  PRODUCTS ||--o{ CART_ITEMS : selected
  PRODUCTS ||--|| INVENTORY : has
  USERS ||--o{ ORDERS : places
  ORDERS ||--o{ ORDER_ITEMS : contains
  PRODUCTS ||--o{ ORDER_ITEMS : snapshots
  ORDERS ||--o| PAYMENTS : has
  ORDERS ||--o{ OUTBOX_EVENTS : emits
  USERS ||--o{ IDEMPOTENCY_RECORDS : submits
  USERS { uuid id PK string email UK string password_hash string role datetime created_at }
  PRODUCTS { uuid id PK string sku UK string name int unit_price_minor bool active }
  INVENTORY { uuid product_id PK/FK int available_quantity int reserved_quantity datetime updated_at }
  CARTS { uuid id PK uuid user_id FK datetime created_at datetime updated_at }
  CART_ITEMS { uuid cart_id PK/FK uuid product_id PK/FK int quantity }
  ORDERS { uuid id PK uuid user_id FK string status int total_amount_minor datetime created_at datetime updated_at }
  ORDER_ITEMS { uuid id PK uuid order_id FK uuid product_id FK string product_name string sku int unit_price_minor int quantity int line_total_minor }
  PAYMENTS { uuid id PK uuid order_id UK string provider_reference string status int amount_minor string idempotency_key }
  OUTBOX_EVENTS { uuid id PK string event_type string aggregate_id json payload datetime published_at }
  IDEMPOTENCY_RECORDS { uuid id PK uuid user_id FK string key response_hash string response_body UK }
```

Expected constraints include unique user email, product SKU, one inventory row per product, one active cart per user where configured, positive quantities/prices, non-negative inventory, valid foreign keys, and unique `(user_id, idempotency_key)`. Indexes should support actual access paths: email/SKU lookup, product active/search listing, order-by-user and order-created time, outbox unpublished rows, and payment provider/idempotency lookup.

Checkout performs a transaction covering inventory locks, order/item snapshots, payment intent, outbox event, idempotency record, and cart consumption. Alembic owns schema evolution; production applies migrations as a controlled release step rather than relying on application startup.
