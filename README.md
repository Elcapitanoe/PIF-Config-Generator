# PIF Config Generator

Automated pipeline for tracking Android build properties and compiling validated Play Integrity Fix (PIF) JSON profiles.

```
Upstream Repositories
  ├── Pixel-Props/build.prop (Stable)
  └── Elcapitanoe/Build-Prop-BETA (Beta)
            │
            ▼
  [ pif-gen check ] ─── Poll tags vs local state/
            │
            ▼ (On tag update)
  [ pif-gen build ] ─── Download ZIPs ──> Extract system.prop ──> Parse & Validate
            │
            ▼
  [ pif-gen publish ] ─ Deploy unified release bundle (vYY.MMDD)
```

---

## Schema Reference

Properties are resolved across partition namespaces (`system_ext` > `system` > `product` > `vendor`) and validated against Pydantic schemas.

### Extended Profile Schema

| Key | Property Resolution Order | Description |
|:---|:---|:---|
| `ID` | `ro.system_ext.build.id` → `ro.system.build.id` → `ro.build.id` → `ro.vendor.build.id` | Android build identifier |
| `BRAND` | `ro.product.system_ext.brand` → `ro.product.system.brand` → `ro.product.brand` | Device brand (`google`) |
| `DEVICE` | `ro.product.system_ext.device` → `ro.product.system.device` → `ro.product.device` | Hardware board codename |
| `MANUFACTURER` | `ro.product.system_ext.manufacturer` → `ro.product.manufacturer` | Hardware manufacturer |
| `MODEL` | `ro.product.system_ext.model` → `ro.product.system.model` → `ro.product.model` | Commercial model name |
| `PRODUCT` | `ro.product.system_ext.name` → `ro.product.system.name` → `ro.product.name` | Product codename |
| `FINGERPRINT` | `ro.system_ext.build.fingerprint` → `ro.build.fingerprint` → `ro.vendor.build.fingerprint` | Build fingerprint |
| `SECURITY_PATCH` | `ro.build.version.security_patch` → parsed date pattern | Patch date (`YYYY-MM-DD`) |
| `DEVICE_INITIAL_SDK_INT` | `ro.product.first_api_level` → `ro.board.first_api_level` → `ro.system.build.version.sdk` | Factory launch SDK |
| `RELEASE` | `ro.system_ext.build.version.release` → `ro.build.version.release` | Android OS version |
| `TYPE` | `ro.system_ext.build.type` → `ro.build.type` | Build type (`user`) |
| `TAG` | `ro.system_ext.build.tags` → `ro.build.tags` | Signing key tag (`release-keys`) |
| `DEBUG` | Evaluated (`ro.debuggable == 1` or `TYPE != user`) | Debug build flag (`false`) |

The profile behavior flags are model defaults, not values extracted from `system.prop`. Their defaults now match the supplied v2 example: `spoofProps` is set to `"1"` and `spoofVendingBuild` is set to `"1"`.

### Generated Output Example

```json
{
  "ID": "CP41.260814.003.B1",
  "BRAND": "google",
  "DEVICE": "komodo",
  "MANUFACTURER": "Google",
  "FINGERPRINT": "google/komodo_beta/komodo:17/CP41.260814.003.B1/16166531:user/release-keys",
  "MODEL": "Pixel 9 Pro XL",
  "PRODUCT": "komodo_beta",
  "SECURITY_PATCH": "2026-08-14",
  "DEVICE_INITIAL_SDK_INT": "34",
  "TYPE": "user",
  "TAG": "release-keys",
  "RELEASE": "17",
  "DEBUG": false,
  "spoofBuild": "1",
  "spoofProps": "1",
  "spoofProvider": "0",
  "spoofSignature": "0",
  "spoofVendingSdk": "0",
  "spoofVendingBuild": "1",
  "verboseLogs": "0"
}
```

---

## Installation

### Prerequisites

Install `Python 3.10+`, `pip`, and `git`:

**Ubuntu / Debian / WSL:**
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

**Fedora / RHEL:**
```bash
sudo dnf install -y python3 python3-pip git
```

**Arch Linux:**
```bash
sudo pacman -S --needed python python-pip git
```

**macOS (Homebrew):**
```bash
brew install python git
```

**Windows:**
Install Python 3.10+ via [python.org](https://www.python.org/downloads/) or winget:
```powershell
winget install Python.Python.3.12 Git.Git
```

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/Elcapitanoe/pif-config-generator.git
cd pif-config-generator

# 2. Create and activate an isolated virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Upgrade pip and install package in editable mode with dev tools
pip install --upgrade pip
pip install -e ".[dev]"
```

Verify the installation:

```bash
pif-gen --help
```

---

## Usage

### 1. Build a Single Profile Locally

Generate a validated PIF JSON profile from a local `system.prop` or property dump. No network access or GitHub token required.

```bash
pif-gen build --file path/to/system.prop --output-dir output
```

Or extract directly from a remote ZIP URL:

```bash
pif-gen build --url "https://github.com/.../device.zip" --output-dir output
```

Options:
- `--file <path>`: Path to the input property dump file.
- `--url <url>`: Direct URL to an upstream property ZIP archive.
- `--output-dir <dir>`: Destination directory for the generated JSON file (defaults to current directory `.`).
- `--format <extended|legacy>`: Profile schema to target (`extended` for modern modules, `legacy` for older modules; default: `extended`).
- `--channel <stable|beta>`: Prefix ZIP-derived profile filenames by upstream channel to keep Stable and Beta artifacts distinct (default: `stable`).

#### Capturing device properties with ADB

To dump build properties directly from a connected Android device:

```bash
adb shell getprop | sed -r 's/\[(.*)\]: \[(.*)\]/\1=\2/' > system.prop
pif-gen build --file system.prop --output-dir output
```

#### Sample `system.prop`

```properties
ro.system_ext.build.id=CP41.260814.003.B1
ro.product.system_ext.brand=google
ro.product.system_ext.device=komodo
ro.product.system_ext.manufacturer=Google
ro.product.system_ext.model=Pixel 9 Pro XL
ro.product.system_ext.name=komodo_beta
ro.system_ext.build.fingerprint=google/komodo_beta/komodo:17/CP41.260814.003.B1/16166531:user/release-keys
ro.build.version.security_patch=2026-08-14
ro.product.first_api_level=34
ro.system_ext.build.version.release=17
ro.system_ext.build.type=user
ro.system_ext.build.tags=release-keys
ro.debuggable=0
```

---

### 2. Check for Upstream Updates

Poll monitored upstream repositories (`Pixel-Props/build.prop` for stable, `Elcapitanoe/Build-Prop-BETA` for beta) and compare latest releases against local tracking tags in `state/last_<channel>_tag.txt`.

Works unauthenticated for checking public releases (subject to standard GitHub API rate limits), or authenticated via personal access token:

```bash
# Optional: Set token to avoid rate limits
export GITHUB_TOKEN="ghp_xxx"

pif-gen check --state-dir state
```

Options:
- `--state-dir <dir>`: Directory storing release tag state files (default: `state`).
- `--token <token>`: GitHub personal access token (falls back to the `GITHUB_TOKEN` environment variable).

Sample output:

```json
{
  "new_release": true,
  "results": [
    {
      "channel": "beta",
      "tag": "2026.08.14",
      "assets": [
        {
          "name": "Komodo_beta.zip",
          "url": "https://github.com/.../Komodo_beta.zip"
        }
      ],
      "count": 1
    }
  ]
}
```

---

### 3. Batch Build from Asset ZIPs (CI Pipeline)

Download property ZIP archives from URLs, extract `system.prop` in memory, validate against the Pydantic schema, write JSON files to disk, and write a manifest list of generated paths:

```bash
pif-gen build \
  --channel beta \
  --assets-json '[{"name": "Komodo_beta.zip", "url": "https://github.com/.../Komodo_beta.zip"}]' \
  --output-dir output \
  --manifest output/manifest.txt
```

Options:
- `--channel <stable|beta>`: Target release channel for the asset payloads.
- `--assets-json <json>`: JSON array of `{ "name": "...", "url": "..." }` asset descriptors.
- `--output-dir <dir>`: Output directory for generated JSON files.
- `--manifest <path>`: Output text file tracking generated profile paths.

---

### 4. Publish Release to GitHub

Upload generated profiles from a manifest file to GitHub Releases on the target repository using unified daily version tags (`vYY.MMDD`, for example `v26.1023`). The release title is identical to its tag.

```bash
export GITHUB_TOKEN="ghp_xxx"
pif-gen publish \
  --repo "owner/repo" \
  --manifest output/manifest.txt
```

Options:
- `--repo <owner/repo>`: Target GitHub repository.
- `--manifest <path>`: Path to the manifest file containing paths of files to upload.
- `--token <token>`: GitHub personal access token (falls back to `GITHUB_TOKEN`).

---

## Tests

Run the test suite using `pytest`:

```bash
pytest tests/ -v
```

Or using the standard library test runner:

```bash
python3 -m unittest discover tests -v
```

---
