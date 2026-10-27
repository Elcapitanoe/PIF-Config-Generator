import argparse
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from .models import ChannelType, OutputFormat
from .pipeline import PIFPipeline
from .release import ReleaseManager


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=level,
    )


def handle_check(args: argparse.Namespace) -> None:
    manager = ReleaseManager(token=args.token)
    results = manager.check_upstream_updates(state_dir=Path(args.state_dir))

    has_updates = len(results) > 0
    payload = {"new_release": has_updates, "results": results}

    if github_output := os.getenv("GITHUB_OUTPUT"):
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"new_release={'true' if has_updates else 'false'}\n")
            f.write(f"results={json.dumps(results)}\n")

    print(json.dumps(payload, indent=2))


def handle_build(args: argparse.Namespace) -> None:
    pipeline = PIFPipeline(
        channel=ChannelType(args.channel),
        format_type=OutputFormat(args.format),
        output_dir=Path(args.output_dir),
    )

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        profile = pipeline.process_prop_content(content)
        out_path = Path(args.output_dir) / f"{Path(args.file).stem}.json"
        out_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        print(f"Generated: {out_path}")
        return

    if args.url:
        parsed_url = urlparse(args.url)
        asset_name = Path(parsed_url.path).name or "profile.zip"
        dest = pipeline.process_zip_url(asset_name, args.url)
        print(f"Generated: {dest}")
        return

    if args.assets_json:
        assets = json.loads(args.assets_json)
        if not isinstance(assets, list):
            raise ValueError("--assets-json must contain a JSON array.")

        generated_paths = []
        failures = []
        for item in assets:
            try:
                dest = pipeline.process_zip_url(item["name"], item["url"])
                generated_paths.append(str(dest))
            except Exception as exc:
                name = item.get("name", "<unknown>") if isinstance(item, dict) else "<unknown>"
                logging.error("Failed processing %s: %s", name, exc)
                failures.append(name)

        if failures:
            raise RuntimeError(f"Failed to build profile(s): {', '.join(failures)}")
        if not generated_paths:
            raise ValueError("No profiles were generated from --assets-json.")

        if args.manifest:
            Path(args.manifest).write_text("\n".join(generated_paths), encoding="utf-8")

        print(f"Generated {len(generated_paths)} files.")


def handle_publish(args: argparse.Namespace) -> None:
    manager = ReleaseManager(token=args.token)
    files = [
        Path(line.strip())
        for line in Path(args.manifest).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manager.publish_release(
        target_repo=args.repo,
        files=files,
    )


def handle_index(args: argparse.Namespace) -> None:
    manager = ReleaseManager(token=args.token)
    index = manager.build_release_index(
        target_repo=args.repo,
        release_tag=args.release_tag,
    )
    output_path = Path(args.output)
    changed = manager.write_release_index(index, output_path)
    if changed:
        print(f"Updated: {output_path}")
    else:
        print(f"Unchanged: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pif-gen",
        description="Automated Play Integrity profile extraction and release tool.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check
    p_check = subparsers.add_parser(
        "check",
        help="Check upstream repositories for new releases",
        description="Poll upstream repositories and report pending releases based on local tag state.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_check.add_argument("--token", default=None, help="GitHub token (defaults to GITHUB_TOKEN environment variable)")
    p_check.add_argument("--state-dir", default="state", help="Directory storing upstream release tag state files")
    p_check.set_defaults(func=handle_check)

    # Build
    p_build = subparsers.add_parser(
        "build",
        help="Extract and build PIF JSON profiles",
        description="Extract and validate Play Integrity profiles from a local .prop file or batch asset URLs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_build.add_argument("--channel", choices=["stable", "beta"], default="stable", help="Prefix ZIP-derived profile names by upstream channel")
    p_build.add_argument("--format", choices=["extended", "legacy"], default="extended", help="Target PIF JSON schema format")
    p_build.add_argument("--output-dir", default=".", help="Directory to save generated JSON profiles")
    input_group = p_build.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--file", help="Path to a single input property dump file (e.g. system.prop)")
    input_group.add_argument("--url", help="Direct URL to an upstream property ZIP archive")
    input_group.add_argument("--assets-json", help="JSON array of asset descriptors containing 'name' and 'url'")
    p_build.add_argument("--manifest", default="generated_files.txt", help="Path to output manifest listing generated file paths")
    p_build.set_defaults(func=handle_build)

    # Publish
    p_pub = subparsers.add_parser(
        "publish",
        help="Publish generated profiles to a GitHub release",
        description="Upload generated profiles listed in a manifest file to GitHub Releases on the target repository.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_pub.add_argument("--token", default=None, help="GitHub token (defaults to GITHUB_TOKEN environment variable)")
    p_pub.add_argument("--repo", required=True, help="Target GitHub repository in owner/repo format")
    p_pub.add_argument("--manifest", default="generated_files.txt", help="Manifest file containing paths of files to upload")
    p_pub.set_defaults(func=handle_publish)

    # Index
    p_index = subparsers.add_parser(
        "index",
        help="Generate a metadata index for the latest published release",
        description="Write direct URLs, checksums, and device metadata for a GitHub release.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_index.add_argument("--token", default=None, help="GitHub token (defaults to GITHUB_TOKEN environment variable)")
    p_index.add_argument("--repo", required=True, help="Target GitHub repository in owner/repo format")
    p_index.add_argument("--release-tag", default=None, help="Specific release tag (defaults to the latest release)")
    p_index.add_argument("--output", default="releases/latest.json", help="Path for the generated release index")
    p_index.set_defaults(func=handle_index)

    args = parser.parse_args()
    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
