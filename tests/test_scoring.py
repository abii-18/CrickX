import copy
import unittest
from cricx.events import validate
from cricx.fixtures import fixture
from cricx.scoring import score


class ScoringTests(unittest.TestCase):
    def test_hand_calculated_innings(self):
        innings = score(fixture())[("demo-001", 1)]
        self.assertEqual((innings["runs"], innings["wickets"], innings["legal_balls"], innings["extras"]), (17, 2, 6, 4))
        self.assertEqual(innings["batting"]["Batter A"]["runs"], 13)
        self.assertEqual(innings["batting"]["Batter A"]["balls"], 7)
        self.assertEqual(innings["bowling"]["Bowler X"], {"runs": 15, "legal_balls": 6, "wickets": 1})

    def test_duplicates_and_out_of_order(self):
        events = fixture()
        self.assertEqual(score(events), score(list(reversed(events)) + events))

    def test_correction_and_stale_revision(self):
        events = fixture()
        correction = copy.deepcopy(events[1])
        correction.update(revision_number=2, event_id="corrected", batter_runs=6)
        result = score(events + [correction, events[1]])[("demo-001", 1)]
        self.assertEqual(result["runs"], 19)
        self.assertEqual(result["batting"]["Batter A"]["fours"], 0)

    def test_conflicting_revision(self):
        events = fixture()
        conflict = copy.deepcopy(events[0])
        conflict.update(event_id="conflict", batter_runs=2)
        with self.assertRaisesRegex(ValueError, "conflicting payload"):
            score(events + [conflict])

    def test_innings_isolation(self):
        second = copy.deepcopy(fixture()[0])
        second.update(innings_number=2, event_id="innings-two")
        result = score(fixture() + [second])
        self.assertEqual(result[("demo-001", 1)]["runs"], 17)
        self.assertEqual(result[("demo-001", 2)]["runs"], 1)

    def test_invalid_payloads(self):
        for change in ({"batter_runs": -1}, {"revision_number": True}, {"event_time": "bad"}, {"wicket_type": "bowled"}):
            event = copy.deepcopy(fixture()[0]); event.update(change)
            with self.assertRaises(ValueError):
                validate(event)

    def test_leg_byes_excluded_from_bowler(self):
        event = copy.deepcopy(fixture()[0])
        event.update(batter_runs=0)
        event["extras"]["leg_byes"] = 3
        innings = score([event])[("demo-001", 1)]
        self.assertEqual((innings["runs"], innings["legal_balls"]), (3, 1))
        self.assertEqual(innings["bowling"]["Bowler X"]["runs"], 0)

    def test_wide_stumping(self):
        event = copy.deepcopy(fixture()[2])
        event.update(wicket_type="stumped", player_out="Batter A")
        innings = score([event])[("demo-001", 1)]
        self.assertEqual((innings["runs"], innings["wickets"], innings["legal_balls"]), (1, 1, 0))
        self.assertEqual(innings["batting"]["Batter A"]["balls"], 0)
        self.assertEqual(innings["bowling"]["Bowler X"]["wickets"], 1)


if __name__ == "__main__":
    unittest.main()
