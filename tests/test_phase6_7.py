"""Tests for Phase 6 (SQLiteSessionManager) and Phase 7 (SettingsManager)."""
import os
import tempfile
import unittest

from services.db import SQLiteSessionManager
from services.settings_manager import SettingsManager


class SQLiteSessionManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.sm = SQLiteSessionManager(storage_dir=self.tmpdir)

    def test_start_and_log(self):
        sid = self.sm.start_session("alice")
        self.assertTrue(sid.startswith("alice-"))
        self.sm.log_interaction(sid, {"query": "hello", "response": "world"})
        session = self.sm.get_session(sid)
        self.assertEqual(session["user_id"], "alice")
        self.assertEqual(len(session["interactions"]), 1)
        self.assertEqual(session["interactions"][0]["query"], "hello")

    def test_intent_persistence(self):
        sid = self.sm.start_session("bob")
        intent = {"location": "London", "sections": ["weather", "news"]}
        self.sm.save_intent(sid, intent)
        self.assertEqual(self.sm.get_intent(sid), intent)

    def test_save_briefing(self):
        sid = self.sm.start_session("carol")
        self.assertFalse(self.sm.is_saved(sid))
        ok = self.sm.save_briefing(sid, {"weather": {"status": "success"}})
        self.assertTrue(ok)
        self.assertTrue(self.sm.is_saved(sid))
        session = self.sm.get_session(sid)
        self.assertIsNotNone(session["last_sections"])

    def test_list_sessions(self):
        for name in ("u1", "u2", "u3"):
            sid = self.sm.start_session(name)
            self.sm.log_interaction(sid, {"query": f"query from {name}"})
        sessions = self.sm.list_sessions(limit=10)
        self.assertEqual(len(sessions), 3)
        # newest first
        self.assertEqual(sessions[0]["user_id"], "u3")

    def test_get_session_not_found(self):
        self.assertIsNone(self.sm.get_session("nonexistent-session"))

    def test_delete_session(self):
        sid = self.sm.start_session("delete-user")
        self.sm.log_interaction(sid, {"query": "temporary"})
        self.assertIsNotNone(self.sm.get_session(sid))
        
        # Delete session
        ok = self.sm.delete_session(sid)
        self.assertTrue(ok)
        self.assertIsNone(self.sm.get_session(sid))
        
        # Deleting non-existent session
        ok = self.sm.delete_session("nonexistent-session")
        self.assertFalse(ok)

    def test_clear_history(self):
        sid1 = self.sm.start_session("user1")
        sid2 = self.sm.start_session("user2")
        self.assertEqual(len(self.sm.list_sessions()), 2)
        
        # Clear history
        ok = self.sm.clear_history()
        self.assertTrue(ok)
        self.assertEqual(len(self.sm.list_sessions()), 0)


class SettingsManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mgr = SettingsManager(storage_dir=self.tmpdir)

    def test_defaults_when_no_file(self):
        s = self.mgr.load()
        self.assertEqual(s["units"], "metric")
        self.assertIn("weather", s["default_sections"])

    def test_save_and_reload(self):
        self.mgr.save({"default_location": "Tokyo", "units": "imperial"})
        s = self.mgr.load()
        self.assertEqual(s["default_location"], "Tokyo")
        self.assertEqual(s["units"], "imperial")

    def test_invalid_units_ignored(self):
        self.mgr.save({"units": "furlongs"})
        s = self.mgr.load()
        self.assertEqual(s["units"], "metric")  # default preserved

    def test_invalid_sections_filtered(self):
        self.mgr.save({"default_sections": ["weather", "invalid_section"]})
        s = self.mgr.load()
        self.assertEqual(s["default_sections"], ["weather"])


if __name__ == "__main__":
    unittest.main()
