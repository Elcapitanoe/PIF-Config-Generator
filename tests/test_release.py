import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from pif_generator.release import MonitoredRepo, ReleaseManager


class TestReleaseManager(unittest.TestCase):
    def test_unauthenticated_init(self):
        with patch.dict("os.environ", {}, clear=True):
            manager = ReleaseManager(token=None)
            self.assertIsNone(manager.token)
            self.assertIsNotNone(manager.client)

    def test_publish_requires_token(self):
        with patch.dict("os.environ", {}, clear=True):
            manager = ReleaseManager(token=None)
            with self.assertRaises(ValueError):
                manager.publish_release(target_repo="dummy/repo", files=[])

    def test_publish_requires_artifacts(self):
        manager = ReleaseManager(token="token")
        with self.assertRaisesRegex(ValueError, "At least one artifact"):
            manager.publish_release(target_repo="dummy/repo", files=[])

    def test_check_propagates_unexpected_error(self):
        manager = ReleaseManager(token="token")
        manager.client = MagicMock()
        manager.client.get_repo.side_effect = RuntimeError("GitHub unavailable")

        with TemporaryDirectory() as tmp_dir:
            with self.assertRaisesRegex(RuntimeError, "GitHub unavailable"):
                manager.check_upstream_updates(
                    repos=[MonitoredRepo(owner="owner", name="repo", channel="stable")],
                    state_dir=Path(tmp_dir),
                )

    @patch("pif_generator.release.datetime")
    def test_publish_uses_tag_as_title(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2026, 10, 23, tzinfo=timezone.utc)
        manager = ReleaseManager(token="token")
        manager.client = MagicMock()
        repo = manager.client.get_repo.return_value
        release = repo.create_git_release.return_value
        release.get_assets.return_value = []

        with TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "stable_komodo.json"
            artifact.write_text("{}", encoding="utf-8")
            manager.publish_release(target_repo="owner/repo", files=[artifact])

        create_call = repo.create_git_release.call_args.kwargs
        self.assertEqual(create_call["tag"], "v26.1023")
        self.assertEqual(create_call["name"], "v26.1023")
        self.assertIn("`v26.1023`", create_call["message"])


if __name__ == "__main__":
    unittest.main()
