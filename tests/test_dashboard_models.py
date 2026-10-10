import unittest
from cricx.fixtures import fixture
from dashboard.models import summarize


class DashboardModelsTests(unittest.TestCase):
    def test_hand_calculated_cards(self):
        result = summarize(fixture(), 20)
        self.assertEqual(result["progress"][-1], {"overs": 1.0, "runs": 17})
        self.assertEqual(result["wickets"], [
            {"#": 1, "Score": 11, "Over": "0.4", "Player": "Batter B"},
            {"#": 2, "Score": 17, "Over": "1.0", "Player": "Batter A"}])
        self.assertEqual(result["last_partnership"]["runs"], 6)
        self.assertEqual(result["last_partnership"]["balls"], 2)
        self.assertEqual([d["marker"] for d in result["deliveries"]], ["1", "4", "Wd", "Nb", "2", "W", "6", "W"])
        self.assertEqual(result["phases"][0]["RR"], "17.00")
