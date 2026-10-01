# Security

## Controls

- Passwords are stored as Argon2 hashes; plaintext passwords are never persisted or logged.
- JWT access tokens are signed with environment-provided secrets and short, explicit lifetimes.
- Customer/admin authorization is enforced at resource boundaries, including ownership checks for carts and orders.
- Pydantic validation and parameterized SQLAlchemy statements constrain user input; totals are recomputed server-side.
- Checkout and login can be rate-limited through Redis counters with namespaced keys and expiry.
- Webhooks require HMAC/shared-secret verification and idempotent event handling.
- Errors are structured without stack traces, credentials, or provider secrets.
- Secrets belong in environment/secret-manager configuration, never in committed `.env` files.

## Threat model

Attackers may submit malformed payloads, replay checkout requests/webhooks, guess credentials, access another user's identifiers, or exploit leaked tokens. The principal mitigations are validation, authentication, authorization, rate limits, idempotency, ownership filters, secure transport at the edge, and key rotation. Redis cache entries must not accidentally expose private data; product detail is public/cacheable, user/order data is not.

For production, add TLS termination, secure cookie/token policy as appropriate, audit logs, dependency scanning, secret rotation, database least privilege, network segmentation, and an incident response procedure. Local demo credentials are never production credentials.
