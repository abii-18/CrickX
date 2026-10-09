"""Real PostgreSQL tests; opt in using CRICX_TEST_DATABASE_URL."""
import copy
import json
import os
import unittest
import uuid
from unittest.mock import patch

DSN = os.getenv("CRICX_TEST_DATABASE_URL")


@unittest.skipUnless(DSN, "requires disposable PostgreSQL test connection")
class StoreTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from cricx.store import initialize
        from cricx.fixtures import fixture
        self.psycopg = psycopg
        initialize(DSN)
        self.match = "test-" + uuid.uuid4().hex
        self.events = fixture(self.match)

    def records(self, events):
        return [(f"{self.match}:{i}", json.dumps(e)) for i, e in enumerate(events)]

    def totals(self):
        with self.psycopg.connect(DSN) as conn:
            return conn.execute("SELECT runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s", (self.match,)).fetchone()

    def tearDown(self):
        with self.psycopg.connect(DSN) as conn:
            for table in ("over_summary", "batting_scorecard", "bowling_scorecard", "innings_scorecard", "delivery_events"):
                conn.execute(f"DELETE FROM {table} WHERE match_id=%s", (self.match,))
            conn.execute("DELETE FROM rejected_events WHERE source_key LIKE %s", (self.match + ":%",))
            conn.execute("DELETE FROM matches WHERE match_id=%s", (self.match,))

    def test_replay_and_out_of_order(self):
        from cricx.store import persist
        persist(DSN, self.records(list(reversed(self.events))))
        self.assertEqual(self.totals(), (17, 2, 6, 4))
        persist(DSN, self.records(self.events))
        self.assertEqual(self.totals(), (17, 2, 6, 4))

    def test_correction_atomic_and_audited(self):
        from cricx.store import persist
        persist(DSN, self.records(self.events))
        e = copy.deepcopy(self.events[1])
        e.update(revision_number=2, event_id=f"{self.match}:correction", batter_runs=6)
        persist(DSN, [(f"{self.match}:fix", json.dumps(e))])
        self.assertEqual(self.totals(), (19, 2, 6, 4))
        persist(DSN, self.records(self.events))
        self.assertEqual(self.totals(), (19, 2, 6, 4))
        with self.psycopg.connect(DSN) as conn:
            history = conn.execute("SELECT revision_history FROM delivery_events WHERE match_id=%s AND raw_delivery_sequence=2", (self.match,)).fetchone()[0]
            self.assertEqual(history, [self.events[1]])

    def test_rebuild_failure_rolls_back_ledger(self):
        from cricx.store import persist
        with patch("cricx.store.score", side_effect=RuntimeError("injected rebuild failure")):
            with self.assertRaises(RuntimeError):
                persist(DSN, self.records(self.events))
        with self.psycopg.connect(DSN) as conn:
            count = conn.execute("SELECT count(*) FROM delivery_events WHERE match_id=%s", (self.match,)).fetchone()[0]
            self.assertEqual(count, 0)
        persist(DSN, self.records(self.events))
        self.assertEqual(self.totals(), (17, 2, 6, 4))

    def test_invalid_event_audit_is_retry_safe(self):
        from cricx.store import persist
        records = [(f"{self.match}:invalid", "{broken json")]
        persist(DSN, records); persist(DSN, records)
        self.assertIsNone(self.totals())
        with self.psycopg.connect(DSN) as conn:
            count = conn.execute("SELECT count(*) FROM rejected_events WHERE source_key=%s", (records[0][0],)).fetchone()[0]
            self.assertEqual(count, 1)
