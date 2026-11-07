# PIF Config Generator

PIF Config Generator turns Android build properties into JSON profiles for Play Integrity Fix (PIF). It reads a local `.prop` file or extracts `system.prop` from a ZIP archive, validates the resulting profile, and writes it in either `extended` or `legacy` format.

After installation, run the tool with `pif-gen`.

## Requirements

- Python 3.11 or later
- A GitHub token for publishing releases or generating the release index

A GitHub token is optional when checking public upstream repositories, unless you reach the unauthenticated API rate limit.

## Install

```bash
git clone https://github.com/Elcapitanoe/PIF-Config-Generator.git
cd PIF-Config-Generator

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Check that the command is available:

```bash
pif-gen --help
```

The runtime dependencies are `requests`, `PyGithub`, and `pydantic`. The `dev` extra also installs `pytest`.

## Build profiles

Each `build` command takes exactly one input source: a local property file, one ZIP URL, or a JSON list of ZIP assets.

### From a local property file

```bash
pif-gen build --file system.prop --output-dir output
```

This creates `output/system.json`. The output name comes from the input file name. In this mode, `--channel` does not affect the output name.

The parser accepts plain `key=value` lines. It skips blank lines, comments beginning with `#`, and lines without `=`. It trims whitespace around keys and values. If a key appears more than once, the last value is used.

To capture properties from a connected Android device with ADB:

```bash
adb shell getprop \
  | sed -E 's/^\[([^]]+)\]: \[([^]]*)\]$/\1=\2/' \
  > system.prop

pif-gen build --file system.prop --output-dir output
```

### From one ZIP URL

Use the Yogi beta build from the `v26.1029` release.

#### Linux

```bash
pif-gen build \
  --url 'https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Yogi_beta_DP11.261016.004.zip' \
  --channel beta \
  --output-dir output
```

#### macOS

```bash
pif-gen build \
  --url 'https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Yogi_beta_DP11.261016.004.zip' \
  --channel beta \
  --output-dir output
```

#### Windows PowerShell

```powershell
pif-gen build `
  --url 'https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Yogi_beta_DP11.261016.004.zip' `
  --channel beta `
  --output-dir output
```

The tool downloads the archive into memory and reads the first entry whose path ends in `system.prop`. The extracted file must be UTF-8 text. This command generates `output/Yogi_beta_DP11.261016.004.json`.

### From several ZIP assets

Pass `--assets-json` a JSON array of objects with `name` and `url` keys:

#### Linux

```bash
pif-gen build \
  --channel beta \
  --assets-json '[
    {"name":"Komodo_beta_DP11.261016.003.zip","url":"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Komodo_beta_DP11.261016.003.zip"},
    {"name":"Tokay_beta_DP11.261016.003.zip","url":"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Tokay_beta_DP11.261016.003.zip"}
  ]' \
  --output-dir output \
  --manifest output/manifest_beta.txt
```

#### macOS

```bash
pif-gen build \
  --channel beta \
  --assets-json '[
    {"name":"Komodo_beta_DP11.261016.003.zip","url":"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Komodo_beta_DP11.261016.003.zip"},
    {"name":"Tokay_beta_DP11.261016.003.zip","url":"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Tokay_beta_DP11.261016.003.zip"}
  ]' \
  --output-dir output \
  --manifest output/manifest_beta.txt
```

#### Windows PowerShell 5.1

PowerShell 5.1 needs `--%` and escaped JSON quotes when passing `--assets-json` to `pif-gen`:

```powershell
pif-gen --% build --channel beta --assets-json [{\"name\":\"Komodo_beta_DP11.261016.003.zip\",\"url\":\"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Komodo_beta_DP11.261016.003.zip\"},{\"name\":\"Tokay_beta_DP11.261016.003.zip\",\"url\":\"https://github.com/Elcapitanoe/Build-Prop-BETA/releases/download/v26.1029/Tokay_beta_DP11.261016.003.zip\"}] --output-dir output --manifest output/manifest_beta.txt
```

These commands use the `v26.1029` beta release and generate `Komodo_beta_DP11.261016.003.json` and `Tokay_beta_DP11.261016.003.json`. To build profiles for other devices or use a newer beta, open the [Build-Prop-BETA releases](https://github.com/Elcapitanoe/Build-Prop-BETA/releases), select the release marked **Latest**, and find the ZIP asset for each device codename. Copy each asset's filename and download URL into the JSON array, replacing both the `name` and `url` values. Keep the release tag and asset filename from the same release.

The manifest lists the generated file paths, one per line. Pass it to `pif-gen publish` to upload those files. `--manifest` is used only with batch input; single-file and single-URL builds print the generated path instead.

### Build options

| Option | Default | Description |
|:--|:--|:--|
| `--file PATH` | — | Read one local property file |
| `--url URL` | — | Download one ZIP archive |
| `--assets-json JSON` | — | Read a JSON list of ZIP assets |
| `--output-dir DIR` | `.` | Directory for generated profiles |
| `--format` | `extended` | Output format: `extended` or `legacy` |
| `--channel` | `stable` | Input channel: `stable` or `beta` |
| `--manifest PATH` | `generated_files.txt` | Write a manifest for batch output |

ZIP requests time out after 120 seconds. In URL and batch modes, beta output names include a `beta` token. Local file output names are unchanged by the channel.

## Output formats

The default format is `extended`:

```bash
pif-gen build --file system.prop --format extended --output-dir output
```

Use `legacy` for consumers that expect the older set of fields:

```bash
pif-gen build --file system.prop --format legacy --output-dir output
```

### Extended format

The generated build fields are:

```text
ID
BRAND
DEVICE
MANUFACTURER
FINGERPRINT
MODEL
PRODUCT
SECURITY_PATCH
DEVICE_INITIAL_SDK_INT
TYPE
TAG
RELEASE
DEBUG
```

The format also includes these PIF settings. They are model defaults, not values read from `system.prop`.

| Field | Default |
|:--|:--:|
| `spoofBuild` | `"1"` |
| `spoofProps` | `"1"` |
| `spoofProvider` | `"0"` |
| `spoofSignature` | `"0"` |
| `spoofVendingSdk` | `"0"` |
| `spoofVendingBuild` | `"1"` |
| `verboseLogs` | `"0"` |

`DEBUG` is true if `ro.debuggable=1` or the resolved build type is `userdebug` or `eng`.

### Legacy format

The legacy profile contains only these fields:

```text
MANUFACTURER
MODEL
FINGERPRINT
BRAND
PRODUCT
DEVICE
SECURITY_PATCH
FIRST_API_LEVEL
```

## Property lookup

For each `extended` field, the tool uses the first non-empty property in the listed order.

| Field | Property lookup order |
|:--|:--|
| `ID` | `ro.system_ext.build.id`, `ro.system.build.id`, `ro.build.id`, `ro.vendor.build.id`, `ro.system_dlkm.build.id` |
| `BRAND` | `ro.product.system_ext.brand`, `ro.product.system.brand`, `ro.product.brand` |
| `DEVICE` | `ro.product.system_ext.device`, `ro.product.system.device`, `ro.product.device`, `ro.build.product`, `ro.product.board` |
| `MANUFACTURER` | `ro.product.system_ext.manufacturer`, `ro.product.system.manufacturer`, `ro.product.manufacturer` |
| `MODEL` | `ro.product.system_ext.model`, `ro.product.system.model`, `ro.product.model` |
| `PRODUCT` | `ro.product.system_ext.name`, `ro.product.system.name`, `ro.product.name`, `ro.build.product`, `ro.product.system_ext.device`, `ro.product.device`, `ro.product.board` |
| `FINGERPRINT` | `ro.system_ext.build.fingerprint`, `ro.system.build.fingerprint`, `ro.build.fingerprint`, `ro.product.build.fingerprint`, `ro.bootimage.build.fingerprint`, `ro.vendor.build.fingerprint`, `ro.system_dlkm.build.fingerprint` |
| `DEVICE_INITIAL_SDK_INT` | `ro.product.first_api_level`, `ro.board.first_api_level`, `ro.board.api_level`, `ro.system_ext.build.version.sdk`, `ro.system.build.version.sdk`, `ro.build.version.sdk` |
| `RELEASE` | `ro.system_ext.build.version.release`, `ro.system.build.version.release`, `ro.build.version.release`, `ro.build.version.release_or_codename` |
| `TYPE` | `ro.system_ext.build.type`, `ro.system.build.type`, `ro.build.type` |
| `TAG` | `ro.system_ext.build.tags`, `ro.system.build.tags`, `ro.build.tags` |

For `SECURITY_PATCH`, these properties are checked first:

```text
ro.build.version.security_patch
ro.vendor.build.security_patch
ro.system.build.version.security_patch
```

A direct value is used only if it is 10 characters long. If none qualifies, the tool extracts a date from the build ID, then from the fingerprint. For example, `BP3A.251005.004` produces `2025-10-05`.

The `extended` builder defaults `BRAND` to `google`, `MANUFACTURER` to `Google`, `MODEL` to `Unknown`, `TYPE` to `user`, `TAG` to `release-keys`, and the SDK value to `0`. The SDK value is still validated, so the `0` fallback normally causes incomplete input to fail validation.

## Validation

Profiles are validated before they are written:

- `SECURITY_PATCH` must be a valid calendar date in `YYYY-MM-DD` format.
- `DEVICE_INITIAL_SDK_INT` and `FIRST_API_LEVEL` must be numeric strings with a value of at least `21`.
- Required string fields cannot be empty.
- A ZIP archive must contain a readable `system.prop` file.
- In batch mode, failures are logged for each asset and the command exits with an error after processing the list.

## Check for upstream releases

The `check` command looks for new tags in these upstream repositories and compares them with the local state files:

| Channel | Repository | State file |
|:--|:--|:--|
| stable | [Pixel-Props/build.prop](https://github.com/Pixel-Props/build.prop) | `state/last_stable_tag.txt` |
| beta | [Elcapitanoe/Build-Prop-BETA](https://github.com/Elcapitanoe/Build-Prop-BETA) | `state/last_beta_tag.txt` |

```bash
pif-gen check --state-dir state
```

A GitHub token is optional for public repositories. If you hit the unauthenticated API rate limit, set `GITHUB_TOKEN` and run the command again:

```bash
export GITHUB_TOKEN='github_pat_...'
pif-gen check --state-dir state
```

In PowerShell, set the variable with `$env:GITHUB_TOKEN = 'github_pat_...'`.

The command prints JSON containing `new_release` and a result for each channel with a new release. Each result includes its channel, tag, asset URLs, and asset count. `check` reads the files in `state/` but does not update them. GitHub Actions updates the tag after a successful build.

## Publish a release

Use `publish` to upload the files listed in a manifest to GitHub Releases:

```bash
export GITHUB_TOKEN='github_pat_...'

pif-gen publish \
  --repo owner/repository \
  --manifest output/manifest.txt
```

Before connecting to GitHub, the command checks that a token is available, the manifest is not empty, every listed file exists, and no two files have the same name. The token needs permission to read the repository and create releases. The workflow grants `contents: write` to its publish job.

Release tags use the current UTC date in `vYY.MMDD` format. For example, October 23, 2026 produces `v26.1023`. The release title matches the tag. If the release already exists, it is reused, and assets with existing filenames are skipped. Upload failures are reported after the remaining files have been attempted.

## Latest release index

The `.github/workflows/update-latest-index.yml` workflow updates `releases/latest.json` after the profile generation workflow succeeds. It can also be started manually from GitHub Actions.

The index selects the newest published release for stable and beta independently, so the channels can point to different release tags. It is committed only when its contents change.

Raw index URL:

```text
https://raw.githubusercontent.com/Elcapitanoe/PIF-Config-Generator/main/releases/latest.json
```

The `channels.stable` and `channels.beta` objects contain release metadata and profile entries. Each profile entry includes its filename, immutable release download URL, SHA-256 checksum, size, channel, codename, device name, and manufacturer. These device details come from the profile: `DEVICE` is the codename, `MODEL` is the device name, and `MANUFACTURER` is the manufacturer.

The index also records the generator repository, package version, and release tag. Consumers can read the index and download profiles without using the GitHub API.

To generate or repair the index manually:

```bash
export GITHUB_TOKEN='github_pat_...'
pif-gen index --repo owner/repository --output releases/latest.json
```

## GitHub Actions automation

`.github/workflows/generate-pif.yml` runs daily at 02:00 UTC and can also be started manually. It:

1. installs the package and runs the test suite;
2. checks for upstream releases;
3. builds stable and beta assets in parallel when new releases are found;
4. validates the generated JSON files;
5. combines the files into one manifest;
6. publishes a GitHub Release;
7. updates the upstream tag state files.

The state update runs `git pull --rebase origin main` and pushes to `main`, so this workflow assumes that branch exists. After the generation workflow succeeds, the index workflow independently finds the latest stable and beta releases, writes `releases/latest.json`, validates it, and commits it to the default branch if it changed.

## Development

Install the development dependencies and run the tests:

```bash
python -m pip install -e '.[dev]'
pytest tests/
```

Source code is in `src/pif_generator/`:

- `builder.py`: parses properties, extracts ZIP contents, and builds profiles
- `models.py`: defines Pydantic models and validators
- `pipeline.py`: coordinates profile generation and output filenames
- `release.py`: handles GitHub API operations
- `cli.py`: defines the `pif-gen` command-line interface
