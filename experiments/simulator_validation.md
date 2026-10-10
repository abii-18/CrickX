# Simulator and database recovery — October 10, 2026

Actual observations from the local Docker deployment; no cloud deployment yet.

- All 14 scoring, simulator and PostgreSQL tests passed. Simulator tests cover
  20 seeds, stable identities, no dismissed batter returning, legal-ball limits,
  wickets and chase termination. These are invariant checks, not full cricket-law proof.
- Two-over seed 42 at 100 acknowledged sends/second produced 17 canonical events:
  Falcons 14/0 from 12 legal balls, Titans 15/0 from 5 legal balls.
  This is a functional smoke test, not a sustained throughput benchmark.
- Streamlit AppTest rendered both innings with no exceptions.
- Restarting the simulator retained match `sim-e82ebe338e90`, cursor 17 and paused state.
- Stopped only CricX PostgreSQL, then generated a second match. Spark's canonical
  query terminated with `psycopg.OperationalError` while the database was absent.
- Restored PostgreSQL. Automatic Spark restart replayed the pending checkpoint batch.
  Canonical batch 3 accepted all 17 events for `sim-faad0134d1a9` and rebuilt
  exactly the same two innings totals. The existing-match verifier passed.
- No volumes/checkpoints were deleted for recovery.

Reproduce the smoke test inside a rebuilt dashboard container:

```powershell
docker compose exec -T dashboard python tests/verify_simulator.py
```

For a deliberately queued match after an outage, add `--existing`; this verifies
the current run rather than starting another match. Do not treat producer completion
as evidence of sink completion: the verifier waits for committed canonical events.

Additional completed experiments:

- Isolated Kafka topic: two consumers in one group owned partitions `[0,1]` and
  `[2]`, consuming 30 unique records together. Another group read all 30 independently.
  Each of three match keys retained its published sequence order. The temporary
  topic was deleted. This proves partition sharing and replay, not broker failover.
- Watermark reached `2026-10-10T12:06:08Z`. One later-arriving delivery timestamped
  `12:05:09Z` was dropped by windows; canonical match `late-8622e3209e29` retained
  all three deliveries and scored 6/0, two legal balls and one extra. Window state
  reported four shuffle partitions.
- Finite burst `burst-b3a8783d-`: 2,400 messages became 1,200 canonical deliveries
  across 150 matches. Every innings scored 17/2, six legal balls and four extras.
  Publishing took 3.36 seconds; full catch-up took 52.85 seconds from publication
  start. Sampled peak backlog was 2,400. This is one local observation, not a
  production capacity/SLA benchmark.

The watermark experiment intentionally advances the shared synthetic event-time
clock beyond wall time. Subsequent older matches can be dropped from activity
windows while canonical scores remain correct. Use isolated topics/checkpoints
for future comparative event-time experiments; never reset canonical checkpoints
to make analytics look current.

- Stopped Spark explicitly and waited for its real Prometheus availability rule.
  Alertmanager delivered `CricXProcessorUnavailable` with status `firing` to the
  dashboard notification feed at `2026-10-10T06:38:22Z`. Spark was then restored.
  This uses only private Docker-network HTTP; no external messages were sent.

Remaining: cloud image/resource/cost checks,
clean deployment and dashboard polish. Experiment programs live in this directory.
