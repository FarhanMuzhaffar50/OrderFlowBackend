# Reliability

OrderFlow separates durable business state from transient work. The transactional outbox writes an event in the same database transaction as the order/payment change. A publisher/worker claims unpublished events, performs the external action, and marks the event after successful handling. Duplicate delivery is expected and handlers are idempotent.

This solves the classic failure window: the database commit succeeds, the process crashes, and a message publish never occurs. Publishing before commit can send an event for a transaction that later rolls back; publishing after commit without an outbox can lose the event. The outbox does not provide exactly-once execution, but it provides durable intent plus at-least-once delivery, which is the useful contract when consumers are idempotent.

Workers use bounded retries and exponential backoff for retryable provider/network failures. Permanent failures become visible as failed payment/order state and logs/metrics; they should not retry indefinitely. A dead-letter or operator-replay mechanism is a natural production extension.

Health means the process is running. Readiness checks critical dependencies such as PostgreSQL and Redis. Structured logs include severity, timestamp, request ID, and relevant aggregate identifiers. Metrics cover request count/latency and checkout/payment outcomes. Backups, restore drills, alert thresholds, and multi-AZ operation belong to deployment operations rather than this local portfolio implementation.
