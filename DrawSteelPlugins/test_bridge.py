"""Fast checks for active-NPC selection and model output boundaries."""

import unittest
from unittest.mock import patch

import bridge


class NegotiationTests(unittest.TestCase):
    def test_presented_negotiation_selects_npc(self):
        snapshot = {"modDocuments": {"scene": {"data": {
            "dialog": {"dialog": "negotiation"},
            "livedata": {"npcName": "Commissioner Ottaviano Bellafonte"},
        }}}}
        self.assertEqual(
            bridge.active_negotiation(snapshot),
            "Commissioner Ottaviano Bellafonte",
        )

    def test_hidden_or_ended_negotiation_is_not_active(self):
        snapshot = {"modDocuments": {"scene": {"data": {
            "dialog": {"dialog": "other"},
            "livedata": {"npcName": "Commissioner Ottaviano Bellafonte"},
        }}}}
        self.assertIsNone(bridge.active_negotiation(snapshot))
        snapshot["modDocuments"]["scene"]["data"]["dialog"]["dialog"] = "negotiation"
        snapshot["modDocuments"]["scene"]["data"]["livedata"]["ended"] = True
        self.assertIsNone(bridge.active_negotiation(snapshot))


class CombatTests(unittest.TestCase):
    def test_model_cannot_select_an_unlisted_move(self):
        with patch.object(bridge, "run_model", return_value={
            "move_id": "invented", "reason": "", "risk": ""
        }):
            with self.assertRaisesRegex(RuntimeError, "unavailable move"):
                bridge.Bridge("test-game", "test-user").suggest({
                    "actor": "Guard", "scene": "Round 1",
                    "candidates": [{"id": "strike", "score": 2}],
                })


if __name__ == "__main__":
    unittest.main()
