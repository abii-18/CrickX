import unittest
from cricx.simulator import generate_match
from cricx.events import validate
from cricx.scoring import score


class SimulatorTests(unittest.TestCase):
    def test_seeded_replay_and_legal_innings(self):
        for seed in range(20):
            events = generate_match("test", seed, "2026-10-10T00:00:00+00:00", 20)
            self.assertEqual(events, generate_match("test", seed, "2026-10-10T00:00:00+00:00", 20))
            dismissed = set()
            for event in events:
                validate(event)
                self.assertNotIn(event["striker"], dismissed)
                self.assertNotIn(event["non_striker"], dismissed)
                if event["player_out"]:
                    dismissed.add(event["player_out"])
            cards = score(events)
            self.assertEqual(len(cards), 2)
            for card in cards.values():
                self.assertLessEqual(card["legal_balls"], 120)
                self.assertLessEqual(card["wickets"], 10)
            first, second = cards[("test", 1)], cards[("test", 2)]
            self.assertTrue(second["runs"] > first["runs"] or second["wickets"] == 10 or second["legal_balls"] == 120)

    def test_short_demo_and_invalid_configuration(self):
        events = generate_match("short", 42, "2026-10-10T00:00:00+00:00", 2)
        self.assertTrue(all(card["legal_balls"] <= 12 for card in score(events).values()))
        with self.assertRaises(ValueError):
            generate_match("bad", 42, "2026-10-10T00:00:00+00:00", 0)

    def test_odi_rosters_and_bowling_limits(self):
        from cricx.teams import INDIA, AUSTRALIA
        events = generate_match("odi", 42, "2026-10-10T00:00:00+00:00")
        for event in events:
            roster = INDIA if event["innings_number"] == 1 else AUSTRALIA
            self.assertIn(event["striker"], roster)
            self.assertIn(event["non_striker"], roster)
        for card in score(events).values():
            self.assertLessEqual(card["legal_balls"], 300)
            self.assertTrue(all(bowler["legal_balls"] <= 60 for bowler in card["bowling"].values()))
