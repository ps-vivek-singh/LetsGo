import json
import os
import tempfile
import unittest

from services.session_manager import SessionManager


class SessionManagerTests(unittest.TestCase):
    def test_logs_session_interactions_to_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            session_id = manager.start_session("demo-user")
            manager.log_interaction(session_id, {"query": "woke up in the morning", "response": "briefing ready"})

            session_path = os.path.join(tmpdir, f"{session_id}.json")
            self.assertTrue(os.path.exists(session_path))
            with open(session_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["user_id"], "demo-user")
            self.assertEqual(len(payload["interactions"]), 1)
            self.assertEqual(payload["interactions"][0]["query"], "woke up in the morning")

    def test_delete_session_and_clear_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(storage_dir=tmpdir)
            sid1 = manager.start_session("u1")
            sid2 = manager.start_session("u2")
            self.assertEqual(len(manager.list_sessions()), 2)
            
            # Delete one session
            ok = manager.delete_session(sid1)
            self.assertTrue(ok)
            self.assertEqual(len(manager.list_sessions()), 1)
            self.assertEqual(manager.list_sessions()[0]["session_id"], sid2)
            
            # Clear all remaining history
            ok = manager.clear_history()
            self.assertTrue(ok)
            self.assertEqual(len(manager.list_sessions()), 0)


if __name__ == "__main__":
    unittest.main()
