import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from github import Auth, Github, GithubException

logger = logging.getLogger(__name__)


@dataclass
class MonitoredRepo:
    owner: str
    name: str
    channel: str  # "stable" or "beta"


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
