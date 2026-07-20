# HireAI Platform Operations Guide (v1.0 Production Handbook)

> **Status: ARCHITECTURE FREEZE v7.0** | Enterprise Operations & Production Runbook

---

## 1. Architecture Overview
HireAI is a multi-tenant enterprise AI agent platform structured into 4 decoupled layers:
- **Infrastructure**: AI Runtime Engine, PostgreSQL, Redis Event Bus, Distributed Workers, Security Context (7C), Governance Engine (7D).
- **Platform**: AI Playground Sandbox (7E), Agent Marketplace Infrastructure (8A), Marketplace Resolver (8B).
- **Developer**: Agent SDK, Tool SDK, Plugin SDK, Testing SDK, Documentation Generator, `hireai` CLI.
- **Operations**: Usage Metering, Policy-Based Quotas, Entitlement Billing, Real-Time SLA Monitoring, Kubernetes Helm & HPA.

---

## 2. Deployment Topology
Production multi-region Kubernetes cluster deployment layout:
```
                                 Cloudflare Global Anycast CDN
                                              │
                                              ▼
                                 NGINX Ingress Gateway
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
         US-East Primary Cluster                              EU-Central Failover Cluster
  ┌───────────────────────────────────────────┐      ┌───────────────────────────────────────────┐
  │ Gateway Pods (3x)                        │      │ Gateway Pods (2x)                         │
  │ Core API Pods (5x)                       │      │ Core API Pods (2x)                        │
  │ Asynchronous Worker Pods (HPA: 5 - 50x)   │      │ Asynchronous Worker Pods (HPA: 2 - 20x)   │
  │ Primary Postgres (HA DB Cluster)          │      │ Read-Replica Postgres                      │
  │ Redis Cluster (Event Bus & Cache)         │      │ Redis Cluster (Replica)                   │
  └───────────────────────────────────────────┘      └───────────────────────────────────────────┘
```

---

## 3. Runtime Data Flow
End-to-End Execution Sequence:
1. **User / API Request**: Authenticates via `SecurityContext` (7C), generating correlation ID.
2. **Governance Check**: `GovernanceEngine` (7D) evaluates risk score and active policy packs.
3. **Marketplace Resolver**: Checks tool, model, and agent dependency graph resolution (`depends_on`).
4. **Execution Pipeline**: `AgentLoader` executes agent step in isolated container sandbox (7E).
5. **Event Bus & Metering**: `UsageMeteringService` records token usage and dispatches `agent.executed` domain event to Redis event bus.

---

## 4. Disaster Recovery (DR) Procedures
- **RPO Target**: < 1 minute | **RTO Target**: < 5 minutes
- **Database Failover**: Automatic PostgreSQL primary-to-standby promotion via Patroni/PgBouncer.
- **Redis Failover**: Redis Sentinel automatically elects new master if master node fails.
- **Event Bus Recovery**: Unacknowledged messages replayed from Redis stream consumer group lag buffer.

---

## 5. Incident Response
- **Severity 1 (P0 - Outage)**: Primary cluster down ➔ Switch Anycast DNS to secondary cluster ➔ Notify SecOps.
- **Severity 2 (P1 - High Latency)**: Worker queue lag > 1000 tasks ➔ HPA auto-scales worker pods.
- **Severity 3 (P2 - Rate Limit Breach)**: Tenant quota exceeded ➔ Returns HTTP `429 Too Many Requests`.

---

## 6. Upgrade Procedures
- **Zero-Downtime Rolling Deployments**: Kubernetes `maxSurge: 25%`, `maxUnavailable: 0`.
- **Alembic Database Migrations**: Non-breaking schema expansions applied BEFORE code deployment.

---

## 7. Rollback Procedures
- **Database Rollback**: `alembic downgrade -1`.
- **Marketplace Package Rollback**: `MarketplaceInstaller.rollback()` restores `current_version` ➔ `previous_version`.
- **Kubernetes Rollback**: `kubectl rollout undo deployment/hireai-api`.

---

## 8. Capacity Planning
- **Pod Sizing**: Core API (1 vCPU, 2GB RAM), Workers (2 vCPU, 4GB RAM).
- **Postgres Sizing**: 16 vCPU, 64GB RAM, NVMe SSD storage.
- **Auto-Scaling Thresholds**: Scale up when CPU > 70%, RAM > 80%, or Worker Queue Delay > 2.0s.

---

## 9. Monitoring & Alerts
Prometheus Alert Rules:
- `HighAPIErrorRate`: 5xx error rate > 1% over 5m ➔ PagerDuty.
- `WorkerQueueLag`: Queue delay > 5s for 3m ➔ Slack #ops-alerts.
- `GovernanceRiskSpike`: Rejected high-risk actions > 20/min ➔ SecOps Alert.

---

## 10. Performance Service-Level Objectives (SLOs)
| Metric | SLO Target |
|--------|------------|
| API Latency (p95) | < 300 ms (excluding model inference) |
| Worker Queue Delay | < 2.0 s |
| Event Delivery Latency | < 500 ms |
| Playground Session Startup | < 5.0 s |
| Marketplace Package Install | < 10.0 s |

---

## 11. Security Operations (SOC 2 Type II Compliance)
- All secrets stored in HashiCorp Vault / Kubernetes Secrets.
- TLS 1.3 enforced for in-transit traffic, AES-256 for at-rest storage.
- Automated PII redaction scanner intercepts logs before persistence.

---

## 12. Governance Operations
- High-risk policy packs (`FINANCE`, `LEGAL`, `MASS_OUTREACH`) require Human-in-the-Loop approvals.
- Audit log records stored immutably for compliance reporting.

---

## 13. Marketplace Operations
- Automated 6-stage package validation scanner (Manifest, Integrity, Sandbox, Security, Governance, Compatibility).
- Publisher verification badges (`OFFICIAL`, `VERIFIED_PARTNER`).

---

## 14. Developer Operations
- Local offline sandbox testing via `hireai test`.
- Diagnostic CLI command `hireai doctor`.
- Automated Markdown and HTML documentation rendering.

---

## 15. Cloud Operations & FinOps
- Metered tracking of AI tokens, API calls, agent tasks, LLM cost, tool invocations, and storage MB.
- Policy-based quota profiles attached to tenant subscription tiers.
