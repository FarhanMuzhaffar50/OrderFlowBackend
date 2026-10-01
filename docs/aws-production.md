# AWS production mapping

The modular monolith maps cleanly to a small AWS footprint without changing domain boundaries:

| Concern | AWS mapping |
|---|---|
| API and worker containers | ECS/Fargate services and task definitions |
| Container images | ECR repositories with immutable tags |
| PostgreSQL | RDS PostgreSQL, Multi-AZ and automated backups |
| Redis | ElastiCache for Redis, private subnets |
| Ingress | Application Load Balancer with HTTPS listener |
| Secrets | Secrets Manager, injected at task runtime |
| Logs/metrics | CloudWatch Logs, alarms, and dashboards |
| Network | VPC, private subnets for data services, security groups |

An ALB routes API traffic to healthy ECS tasks. A separate worker service consumes outbox/payment work and scales independently. RDS remains authoritative for transactions and row locks; ElastiCache serves product cache/rate limits but is not inventory truth. ECR supplies the same image to both services. Secrets Manager avoids committing JWT/provider keys. CloudWatch receives structured logs and application/platform metrics; add OpenTelemetry/X-Ray if distributed tracing becomes necessary.

Use least-privilege IAM task roles, encrypted data stores, TLS, RDS backups/restore drills, deployment health gates, and migration runbooks. Provisioning an AWS environment incurs cost and operational scope, so this repository intentionally documents the mapping rather than claiming that it has created or operated live infrastructure.
