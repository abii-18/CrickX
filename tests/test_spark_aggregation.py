"""Opt-in real Spark tests, with PostgreSQL tests for acceptance boundaries."""
import copy
import json
import os
import unittest
import uuid
from cricx.fixtures import fixture
from cricx.scoring import score

ENABLED = os.getenv("CRICX_RUN_SPARK_TESTS") == "1"
DSN = os.getenv("CRICX_TEST_DATABASE_URL")


def reference(events):
    return {(match, innings, over): values
            for (match, innings), result in score(events).items()
            for over, values in result["overs"].items()}


def extended(match):
    events = fixture(match)
    for sequence in range(9, 16):
        e = copy.deepcopy(events[0])
        e.update(event_id=f"{match}:{sequence}", raw_delivery_sequence=sequence)
        events.append(e)
    second = copy.deepcopy(events[0])
    second.update(event_id=match + ":innings2", innings_number=2)
    events.append(second)
    return events


@unittest.skipUnless(ENABLED, "opt in with CRICX_RUN_SPARK_TESTS=1 inside Spark image")
class SparkAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyspark.sql import SparkSession
        cls.spark = SparkSession.builder.master("local[2]").appName("CricX-over-tests").config(
            "spark.sql.shuffle.partitions", "4").getOrCreate()
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def compute(self, events):
        from spark.over_aggregation import compute_over_summaries
        return compute_over_summaries(self.spark, events)

    def test_same_over_extras_wickets_reference(self):
        self.assertEqual(self.compute(fixture("single")),
                         {("single", 1, 0): {"runs": 17, "wickets": 2, "legal_balls": 6}})

    def test_multiple_overs_innings_matches_out_of_order(self):
        events = extended("a") + extended("b")
        output = self.compute(list(reversed(events)))
        self.assertEqual(output, reference(events))
        self.assertEqual(output[("a", 1, 1)], {"runs": 6, "wickets": 0, "legal_balls": 6})
        self.assertEqual(output[("a", 1, 2)], {"runs": 1, "wickets": 0, "legal_balls": 1})
        self.assertEqual(output[("a", 2, 0)], {"runs": 1, "wickets": 0, "legal_balls": 1})

    def test_empty(self):
        from spark.over_aggregation import aggregate_overs, SCHEMA
        self.assertEqual(self.compute([]), {})
        self.assertEqual(aggregate_overs(self.spark.createDataFrame([], SCHEMA)).count(), 0)

    @unittest.skipUnless(DSN, "requires PostgreSQL")
    def test_ledger_revisions_duplicates_late_and_conflicts(self):
        import psycopg
        from cricx.store import initialize, persist
        match = "spark-test-" + uuid.uuid4().hex
        events = extended(match)
        calls = []
        def aggregate(canonical):
            calls.append(copy.deepcopy(canonical))
            return self.compute(canonical)
        def records(values, label):
            return [(f"{match}:{label}:{i}", json.dumps(e)) for i, e in enumerate(values)]
        def stored():
            with psycopg.connect(DSN) as conn:
                return {(r[0], r[1], r[2]): dict(zip(("runs", "wickets", "legal_balls"), r[3:]))
                        for r in conn.execute("SELECT match_id,innings_number,over_number,runs,wickets,legal_balls FROM over_summary WHERE match_id=%s", (match,))}
        initialize(DSN)
        try:
            persist(DSN, records(list(reversed(events)) + events, "initial"), aggregate)
            self.assertEqual(stored(), reference(events))
            self.assertEqual(len(calls[0]), len(events))
            # An old event-time correction changes legality, moving subsequent over boundaries.
            correction = copy.deepcopy(events[2])
            correction.update(event_id=match + ":correction", revision_number=2, event_time="2020-01-01T00:00:00Z")
            correction["extras"]["wides"] = 0
            persist(DSN, records([correction], "fix"), aggregate)
            expected = reference(events + [correction])
            self.assertEqual(stored(), expected)
            self.assertNotEqual(expected, reference(events))
            conflict = copy.deepcopy(correction)
            conflict.update(event_id=match + ":conflict", batter_runs=4)
            counts = persist(DSN, records([events[2], conflict, correction], "reject"), aggregate)
            self.assertEqual(counts["rejected"], 2)
            self.assertEqual(counts["duplicate"], 1)
            self.assertEqual(len(calls), 2)  # Untouched/rejected-only batches do no Spark work.
            self.assertEqual(stored(), expected)
            counts = persist(DSN, [(match + ":bad", "{malformed")], aggregate)
            self.assertEqual(counts["rejected"], 1)
            self.assertEqual(persist(DSN, [], aggregate), {})
            self.assertEqual(len(calls), 2)
            with psycopg.connect(DSN) as conn:
                totals = conn.execute("SELECT innings_number,runs,wickets,legal_balls,extras FROM innings_scorecard WHERE match_id=%s ORDER BY innings_number", (match,)).fetchall()
                self.assertEqual(totals, [(1, 23, 2, 14, 3), (2, 1, 0, 1, 0)])
                history = conn.execute("SELECT revision_history FROM delivery_events WHERE match_id=%s AND innings_number=1 AND raw_delivery_sequence=3", (match,)).fetchone()[0]
                self.assertEqual(history, [events[2]])
        finally:
            with psycopg.connect(DSN) as conn:
                for table in ("over_summary", "batting_scorecard", "bowling_scorecard", "innings_scorecard", "delivery_events"):
                    conn.execute(f"DELETE FROM {table} WHERE match_id=%s", (match,))
                conn.execute("DELETE FROM matches WHERE match_id=%s", (match,))
                conn.execute("DELETE FROM rejected_events WHERE source_key LIKE %s", (match + ":%",))
