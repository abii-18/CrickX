> Status: deferred, unexecuted planning. No account or resources have been created.
> These historical cost checks must be reverified before any future deployment.

# One-day cloud demo — preparation, not a deployed environment

Verified October 10, 2026. No account or infrastructure has been created by this project.

## Cost boundary

Proposed target: one home-region OCI `VM.Standard.A1.Flex`, 2 OCPUs, 12 GB RAM,
one 50 GB boot volume. Oracle currently documents 1,500 OCPU-hours and 9,000 GB-hours
monthly for A1 and 200 GB combined boot/block storage. Existing tenancy usage counts
against these totals. Capacity may be unavailable and idle instances may be reclaimed.
Always Free resources have no scheduled expiration; eligibility must be rechecked
in the console immediately before creation.
[Official limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

Keep the account unupgraded. Do not use paid shapes, promotional trial credits,
managed Kafka, managed databases, NAT gateways, load balancers, paid images or extra
storage. If the proposed resource is not explicitly free in your account, stop.
Budgets are alerts, not billing caps. A one-day run would use 48 OCPU-hours and
288 GB-hours, excluding any other resources in your tenancy.

Signup requires a qualifying card. Oracle describes temporary authorization holds,
usually removed in three to five days. This is incompatible with a requirement for
absolutely no temporary card hold. The 30-day trial is separate from Always Free;
we do not depend on it.
[Official signup information](https://www.oracle.com/cloud/free/).

## Technical readiness

- Docker registry manifests verified ARM64 support for Python 3.11.11-slim,
  Spark 3.5.3, Kafka 3.9.0, PostgreSQL 16.8, Prometheus 3.2.1, Grafana 11.6.0
  and Alertmanager 0.28.1. ARM64 execution has not yet been tested.
- Local idle memory snapshot after a Spark restart: roughly 1.13 GiB summed
  container memory. This excludes host overhead and is not peak load usage.
- Cloud overlay caps application memory at about 7.13 GiB in aggregate and rotates
  container logs. Actual cloud build/startup/load tests remain required.
- Local burst/recovery results do not predict performance on the proposed VM.

## Access and capture

Install Docker Engine/Compose on the free ARM Linux VM, clone the repository,
generate a fresh private `.env`, then run from the repository root:

```sh
docker compose -f docker-compose.yml -f deploy/compose.cloud.yml up -d --build
docker compose --profile tools run --rm --build test
docker compose exec -T dashboard python tests/verify_simulator.py
```

No API credentials are committed. SSH keys/passwords should never be pasted into
chat. Permit SSH only from your current IP; retain localhost application bindings.
From your computer, substitute your actual key, username and VM address:

```sh
ssh -i YOUR_KEY -L 8501:127.0.0.1:8501 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 USER@VM_IP
```

Record VM identity/date, console free eligibility, functional scores, Grafana metrics
and failure recovery. Capture screenshots/video before teardown. The dashboard is
reachable through your SSH tunnel; this is a cloud-hosted demo, not a public website.

## Cleanup checklist

After evidence capture, explicitly terminate the demo VM and delete its boot volume,
any demo-only backups, block volumes, reserved addresses and network resources.
Inspect the console inventory and billing/usage records afterward. Docker `down -v`
only removes application volumes; it does not delete cloud infrastructure.

Cloud readiness remains pending account eligibility/capacity, ARM execution,
clean-checkout verification and measured resource use. No paid fallback is authorized.
