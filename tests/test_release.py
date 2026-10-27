import unittest
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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

    @patch("pif_generator.release.requests.get")
    def test_build_release_index_contains_all_assets_and_device_metadata(self, mock_get):
        manager = ReleaseManager(token="token")
        manager.client = MagicMock()

        komodo_content = b'{"DEVICE":"komodo","MODEL":"Pixel 9 Pro","MANUFACTURER":"Google"}'
        tokay_content = b'{"DEVICE":"tokay","MODEL":"Pixel 8","MANUFACTURER":"Google"}'
        stable_asset = SimpleNamespace(
            name="Akita_CP3A.261005.005.json",
            browser_download_url="https://example.test/v26.1011/Akita_CP3A.261005.005.json",
            digest="sha256:" + hashlib.sha256(komodo_content).hexdigest(),
            size=len(komodo_content),
            content_type="application/json",
        )
        beta_asset = SimpleNamespace(
            name="Tokay_beta_DP11.261002.005.json",
            browser_download_url="https://example.test/v26.1023/Tokay_beta_DP11.261002.005.json",
            digest=None,
            size=len(tokay_content),
            content_type="application/json",
        )
        stable_release = SimpleNamespace(
            tag_name="v2026.10.11",
            title="PIF Profiles · 2026.10.11",
            html_url="https://github.com/owner/repo/releases/tag/v2026.10.11",
            published_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
            prerelease=False,
            draft=False,
            get_assets=MagicMock(return_value=[stable_asset]),
        )
        beta_release = SimpleNamespace(
            tag_name="v26.1023",
            title="PIF Profiles · 2026.10.23",
            html_url="https://github.com/owner/repo/releases/tag/v26.1023",
            published_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
            prerelease=False,
            draft=False,
            get_assets=MagicMock(return_value=[beta_asset]),
        )
        manager.client.get_repo.return_value.get_releases.return_value = [beta_release, stable_release]
        mock_get.side_effect = [
            SimpleNamespace(content=tokay_content, raise_for_status=MagicMock()),
            SimpleNamespace(content=komodo_content, raise_for_status=MagicMock()),
        ]

        index = manager.build_release_index(
            target_repo="owner/repo",
            generator_commit="abc1234",
        )

        self.assertEqual(index.generator.repository, "https://github.com/owner/repo")
        self.assertEqual(index.channels["stable"].release.tag, "v2026.10.11")
        self.assertEqual(index.channels["beta"].release.tag, "v26.1023")
        self.assertEqual(index.channels["stable"].files[0].codename, "komodo")
        self.assertEqual(index.channels["stable"].files[0].channel, "stable")
        self.assertEqual(index.channels["beta"].files[0].device_name, "Pixel 8")
        self.assertEqual(index.channels["beta"].files[0].channel, "beta")

    def test_write_release_index_is_idempotent(self):
        from pif_generator.models import (
            ChannelReleaseIndex,
            GeneratorMetadata,
            ReleaseIndex,
            ReleaseIndexFile,
            ReleaseMetadata,
        )

        index = ReleaseIndex(
            generator=GeneratorMetadata(
                name="PIF Config Generator",
                repository="https://github.com/owner/repo",
                version="1.0.0",
            ),
            channels={
                "stable": ChannelReleaseIndex(
                    release=ReleaseMetadata(
                        tag="v26.1023",
                        name="v26.1023",
                        url="https://github.com/owner/repo/releases/tag/v26.1023",
                    ),
                    files=[
                        ReleaseIndexFile(
                            filename="stable_Komodo.json",
                            url="https://example.test/stable_Komodo.json",
                            sha256="a" * 64,
                            size_bytes=2,
                            content_type="application/json",
                        )
                    ],
                )
            },
        )

        with TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "releases" / "latest.json"
            self.assertTrue(ReleaseManager.write_release_index(index, output))
            self.assertFalse(ReleaseManager.write_release_index(index, output))
            self.assertIn('"schema_version": 2', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
