import logging
import os
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from github import Auth, Github, GithubException

from . import __version__
from .models import ChannelReleaseIndex, GeneratorMetadata, ReleaseIndex, ReleaseIndexFile, ReleaseMetadata

logger = logging.getLogger(__name__)


@dataclass
class MonitoredRepo:
    owner: str
    name: str
    channel: Literal["stable", "beta"]


DEFAULT_TARGETS = [
    MonitoredRepo(owner="Pixel-Props", name="build.prop", channel="stable"),
    MonitoredRepo(owner="Elcapitanoe", name="Build-Prop-BETA", channel="beta"),
]


class ReleaseManager:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if self.token:
            self.client = Github(auth=Auth.Token(self.token))
        else:
            self.client = Github()

    def check_upstream_updates(
        self,
        repos: Optional[List[MonitoredRepo]] = None,
        state_dir: Path = Path("state"),
    ) -> List[Dict[str, Any]]:
        targets = repos or DEFAULT_TARGETS
        state_dir = Path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        pending_releases = []

        for target in targets:
            full_repo_name = f"{target.owner}/{target.name}"
            tracker_file = state_dir / f"last_{target.channel}_tag.txt"
            last_tag = tracker_file.read_text(encoding="utf-8").strip() if tracker_file.exists() else ""

            repo = self.client.get_repo(full_repo_name)
            try:
                latest = repo.get_latest_release()
            except GithubException as exc:
                if exc.status == 404:
                    logger.warning("No release found on repository %s", full_repo_name)
                    continue
                raise

            current_tag = latest.tag_name
            if last_tag == current_tag:
                logger.info("%s @ %s is up-to-date", full_repo_name, current_tag)
                continue

            zip_assets = [
                {"name": asset.name, "url": asset.browser_download_url}
                for asset in latest.get_assets()
                if asset.name.endswith(".zip")
            ]

            if not zip_assets:
                logger.warning("Release %s on %s has no ZIP assets", current_tag, full_repo_name)
                continue

            logger.info("Discovered new release %s on %s (%d assets)", current_tag, full_repo_name, len(zip_assets))
            pending_releases.append({
                "channel": target.channel,
                "tag": current_tag,
                "assets": zip_assets,
                "count": len(zip_assets),
            })

        return pending_releases

    def publish_release(
        self,
        target_repo: str,
        files: List[Path],
    ) -> None:
        if not self.token:
            raise ValueError("GitHub access token is required to publish releases.")

        if not files:
            raise ValueError("At least one artifact is required to publish a release.")

        paths = [Path(file_path) for file_path in files]
        missing_paths = [path for path in paths if not path.is_file()]
        if missing_paths:
            missing = ", ".join(str(path) for path in missing_paths)
            raise FileNotFoundError(f"Release artifacts not found: {missing}")

        names = [path.name for path in paths]
        if len(names) != len(set(names)):
            raise ValueError("Release artifact names must be unique.")

        repo = self.client.get_repo(target_repo)
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")

        release_tag = f"v{now:%y.%m%d}"
        title = release_tag

        body = (
            f"### Unified Release\n"
            f"- Release Tag: `{release_tag}`\n"
            f"- Release Date: {date_str} UTC\n"
            f"- Artifacts: {len(paths)} JSON profile(s)\n\n"
            f"Automated build from newly detected upstream releases."
        )

        try:
            release = repo.create_git_release(
                tag=release_tag,
                name=title,
                message=body,
            )
            logger.info("Created release: %s (%s)", release_tag, title)
        except GithubException as exc:
            if exc.status == 422:
                release = repo.get_release(release_tag)
                logger.info("Found existing release: %s", release_tag)
            else:
                raise

        existing_assets = {asset.name: asset for asset in release.get_assets()}
        uploaded, skipped = 0, 0
        failed_uploads = []

        for path in paths:
            if path.name in existing_assets:
                logger.debug("Skipping already uploaded artifact: %s", path.name)
                skipped += 1
                continue

            try:
                release.upload_asset(str(path))
                logger.info("Uploaded artifact: %s", path.name)
                uploaded += 1
            except GithubException as exc:
                logger.error("Failed to upload %s: %s", path.name, exc)
                failed_uploads.append(path.name)

        if failed_uploads:
            names = ", ".join(failed_uploads)
            raise RuntimeError(f"Failed to upload release artifact(s): {names}")

        logger.info("Upload completed. Uploaded: %d, Skipped: %d, Total: %d", uploaded, skipped, len(paths))

    def build_release_index(
        self,
        target_repo: str,
        release_tag: Optional[str] = None,
        generator_commit: Optional[str] = None,
        workflow_run_url: Optional[str] = None,
    ) -> ReleaseIndex:
        """Select the newest published release containing assets for each channel."""
        repo = self.client.get_repo(target_repo)
        releases = [repo.get_release(release_tag)] if release_tag else list(repo.get_releases())
        selected = self._select_latest_channel_releases(releases)
        if not selected:
            raise ValueError("No published JSON profile assets were found for stable or beta channels.")

        channels = {}
        for channel in sorted(selected):
            release, assets = selected[channel]
            files = [self._build_index_file(asset) for asset in assets]
            channels[channel] = ChannelReleaseIndex(
                release=self._release_metadata(release),
                files=files,
            )

        return ReleaseIndex(
            generator=GeneratorMetadata(
                name="PIF Config Generator",
                repository=f"https://github.com/{target_repo}",
                version=__version__,
                commit=generator_commit,
                workflow_run_url=workflow_run_url,
            ),
            channels=channels,
        )

    def _select_latest_channel_releases(self, releases: List[Any]) -> Dict[str, Any]:
        selected = {}
        for release in releases:
            if getattr(release, "draft", False):
                continue

            assets_by_channel = {"stable": [], "beta": []}
            for asset in release.get_assets():
                if not asset.name.lower().endswith(".json"):
                    continue
                channel = self._channel_from_filename(asset.name)
                if channel:
                    assets_by_channel[channel].append(asset)

            for channel, assets in assets_by_channel.items():
                if not assets:
                    continue
                current = selected.get(channel)
                candidate_key = self._release_datetime(release)
                if current is None or candidate_key > current[0]:
                    selected[channel] = (candidate_key, release, sorted(assets, key=lambda asset: asset.name))

        return {channel: (value[1], value[2]) for channel, value in selected.items()}

    def _build_index_file(self, asset: Any) -> ReleaseIndexFile:
        content = self._download_asset(asset.browser_download_url)
        profile_metadata = self._read_profile_metadata(asset.name, content)
        return ReleaseIndexFile(
            filename=asset.name,
            url=asset.browser_download_url,
            sha256=self._asset_sha256(asset, content),
            size_bytes=int(asset.size),
            content_type=asset.content_type or "application/octet-stream",
            channel=self._channel_from_filename(asset.name),
            **profile_metadata,
        )

    @staticmethod
    def _release_metadata(release: Any) -> ReleaseMetadata:
        return ReleaseMetadata(
            tag=release.tag_name,
            name=(getattr(release, "title", None) or getattr(release, "name", None) or release.tag_name),
            url=release.html_url,
            published_at=ReleaseManager._format_datetime(
                getattr(release, "published_at", None) or getattr(release, "created_at", None)
            ),
            prerelease=bool(release.prerelease),
        )

    @staticmethod
    def _release_datetime(release: Any) -> datetime:
        value = getattr(release, "published_at", None) or getattr(release, "created_at", None)
        if value is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def write_release_index(index: ReleaseIndex, output_path: Path) -> bool:
        """Write an index only when its serialized content has changed."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = index.model_dump_json(indent=2, exclude_none=True) + "\n"

        if output_path.exists() and output_path.read_text(encoding="utf-8") == serialized:
            return False

        output_path.write_text(serialized, encoding="utf-8")
        return True

    def _download_asset(self, url: str) -> bytes:
        headers = {"Accept": "application/octet-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        return response.content

    @staticmethod
    def _asset_sha256(asset: Any, content: bytes) -> str:
        digest = getattr(asset, "digest", None) or ""
        if digest.startswith("sha256:"):
            digest = digest.removeprefix("sha256:")
        if digest and len(digest) == 64:
            return digest.lower()
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _read_profile_metadata(filename: str, content: bytes) -> Dict[str, Optional[str]]:
        if not filename.lower().endswith(".json"):
            return {}

        try:
            profile = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Release asset {filename} is not valid UTF-8 JSON.") from exc

        return {
            "codename": profile.get("DEVICE") or None,
            "device_name": profile.get("MODEL") or None,
            "manufacturer": profile.get("MANUFACTURER") or None,
        }

    @staticmethod
    def _channel_from_filename(filename: str) -> Optional[str]:
        tokens = re.split(r"[_\-.]+", Path(filename).stem.lower())
        if "beta" in tokens:
            return "beta"
        return "stable"

    @staticmethod
    def _format_datetime(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
