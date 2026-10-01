# Concurrency and overselling

The critical invariant is `available_quantity >= 0`, and at most the available quantity may be reserved. A naïve implementation reads stock, checks `>= requested`, then writes a lower value. Two requests can both read `1` before either writes, so both believe they succeeded.

OrderFlow uses PostgreSQL row-level locking (`SELECT ... FOR UPDATE`, or the equivalent SQLAlchemy locking option) inside the checkout transaction. The first transaction locks the product's inventory row, validates and updates it, and commits. The second waits; after the first commits, it reads the new quantity and returns an out-of-stock conflict. If the first rolls back, its reservation disappears and the next transaction can evaluate the original state.

```mermaid
sequenceDiagram
  participant A as Checkout A
  participant D as Inventory row
  participant B as Checkout B
  A->>D: BEGIN + SELECT FOR UPDATE
  D-->>A: lock acquired, quantity=1
  B->>D: BEGIN + SELECT FOR UPDATE
  A->>D: reserve 1; COMMIT
  D-->>B: lock released; read quantity=0
  B-->>B: return 409 out of stock; ROLLBACK
```

When an order contains several products, lock rows in deterministic product-ID order to reduce deadlock cycles. Keep the transaction short: do not call the payment provider while holding inventory locks. PostgreSQL's transaction isolation and atomic commit protect the database state; an in-process Python lock would protect only one API process and fail when horizontally scaled or restarted.

The concurrency test must use real PostgreSQL because SQLite does not reproduce PostgreSQL row-lock semantics. Record the actual command and result in `docs/verification.md`; this document describes the intended guarantee, not an unexecuted benchmark.
