# PIF Config Generator

Turn an Android build property dump into a Play Integrity Fix (PIF) JSON profile.

The upstream sources used by this project publish ZIP files, while the profile builder needs the system.prop file inside each archive. The property names also vary by Android partition. This tool handles that extraction, applies a fixed fallback order, validates the result, and writes the profile in either the extended or legacy format.

The installed command is pif-gen.

## What the workflow does

~~~text
GitHub release
      |
      v
  pif-gen check       Find a newer stable or beta tag
      |
      v
  pif-gen build      Download ZIPs, read system.prop, write JSON
      |
      v
  pif-gen publish    Upload the JSON files to one daily release
~~~

The scheduled workflow runs the same three steps. Stable and beta builds are kept separate until the final publish job.

## Install

Python 3.10+ is required.

~~~bash
git clone https://github.com/Elcapitanoe/PIF-Config-Generator.git
cd PIF-Config-Generator

python3 -m venv .venv
source .venv/bin/activate
# PowerShell: .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
~~~

Verify the install:

~~~bash
pif-gen --help
~~~

Runtime dependencies are requests, PyGithub, and pydantic. The dev extra adds pytest.

## Build locally

### From a property file

~~~bash
pif-gen build \
  --file system.prop \
  --output-dir output
~~~

With the default settings this creates output/system.json. The name comes from the input file stem. The --channel value does not change filenames in this mode.

The parser expects plain key=value lines. It skips empty lines, comments beginning with #, and lines without =. Keys and values are stripped. Duplicate keys are allowed; the last value wins.

A property dump can be captured from a connected device:

~~~bash
adb shell getprop \
  | sed -E 's/^\[([^]]+)\]: \[([^]]*)\]$/\1=\2/' \
  > system.prop

pif-gen build --file system.prop --output-dir output
~~~

### From a ZIP URL

~~~bash
pif-gen build \
  --url 'https://example.com/device.zip' \
  --channel stable \
  --output-dir output
~~~

The archive is downloaded into memory. The builder opens the ZIP and uses the first entry whose path ends in system.prop. The extracted file must be UTF-8 text.

A URL build preserves the input asset stem and changes only the extension to `.json`, so an asset named device.zip produces:

~~~text
device.json
~~~

### From several ZIP assets

The batch form takes a JSON array of objects with name and url keys:

~~~bash
pif-gen build \
  --channel beta \
  --assets-json '[
    {"name":"Komodo_beta.zip","url":"https://example.com/Komodo_beta.zip"},
    {"name":"Tokay_beta.zip","url":"https://example.com/Tokay_beta.zip"}
  ]' \
  --output-dir output \
  --manifest output/manifest_beta.txt
~~~

The generated files are named from the asset names:

~~~text
Komodo_beta.json
Tokay_beta.json
~~~

The manifest is a newline-separated list of generated paths. It is the input for pif-gen publish.

--file, --url, and --assets-json are mutually exclusive. --manifest is written by the batch path; the single-file and single-URL paths print the generated path and return.

### Build options

| Option | Default | Behavior |
|:--|:--|:--|
| --file PATH | — | Build from one local property file |
| --url URL | — | Download and build one ZIP |
| --assets-json JSON | — | Build from a JSON array of {name, url} objects |
| --output-dir DIR | . | Create this directory and write profiles there |
| --format | extended | Select extended or legacy output |
| --channel | stable | Select the stable or beta input channel |
| --manifest PATH | generated_files.txt | Write the batch output manifest |

ZIP requests use a 120-second timeout.

## Check for new upstream releases

The monitored repositories and their local tag files are:

| Channel | Repository | State file |
|:--|:--|:--|
| stable | Pixel-Props/build.prop | state/last_stable_tag.txt |
| beta | Elcapitanoe/Build-Prop-BETA | state/last_beta_tag.txt |

Run the check with:

~~~bash
pif-gen check --state-dir state
~~~

A GitHub token is optional for public repositories. Set one if the unauthenticated API limit is a problem:

~~~bash
export GITHUB_TOKEN='github_pat_...'
pif-gen check --state-dir state
~~~

The command prints a JSON payload containing new_release and one result for each channel with a new release:

~~~json
{
  "new_release": true,
  "results": [
    {
      "channel": "beta",
      "tag": "beta-20261020",
      "assets": [
        {
          "name": "Komodo_beta.zip",
          "url": "https://github.com/..."
        }
      ],
      "count": 1
    }
  ]
}
~~~

check reads, but does not update, the files in state/. The Actions workflow writes the new tag after its build job succeeds.

## Publish a release

publish reads one path per line from a manifest:

~~~bash
export GITHUB_TOKEN='github_pat_...'

pif-gen publish \
  --repo owner/repository \
  --manifest output/manifest.txt
~~~

Before talking to GitHub, it checks that a token exists, the manifest is not empty, every path exists, and no two artifacts have the same filename.

Release tags use the current UTC date in vYY.MMDD form. For example, October 23, 2026 produces v26.1023. The release title is the same as the tag.

If that release already exists, it is reused. Existing assets are matched by filename and skipped. Upload failures are collected and reported after the remaining files have been attempted.

The token needs repository read access and permission to create releases. The workflow grants contents: write to its publish job.

## Latest release index

The separate `.github/workflows/update-latest-index.yml` workflow maintains a machine-readable index at:

~~~text
releases/latest.json
~~~

The workflow runs automatically after `generate-pif.yml` succeeds and can also be started manually from GitHub Actions. It independently selects the newest published release for each channel, so stable and beta may point to different release tags. The index is committed only when its content changes.

The raw URL for downstream consumers is:

~~~text
https://raw.githubusercontent.com/Elcapitanoe/PIF-Config-Generator/main/releases/latest.json
~~~

The `channels.stable` and `channels.beta` objects each contain their selected release metadata and profile files. Each JSON profile entry includes its filename, immutable release download URL, SHA-256 checksum, size, channel, codename, device name, and manufacturer. Device metadata comes from the generated profile itself: `DEVICE` is the codename, `MODEL` is the human-readable device name, and `MANUFACTURER` is the manufacturer.

The index also identifies the generator repository, package version, and release tag. Consumers do not need GitHub API access to use the index or download the listed profiles.

To generate the index locally or repair it manually:

~~~bash
export GITHUB_TOKEN='github_pat_...'
pif-gen index \
  --repo owner/repository \
  --output releases/latest.json
~~~

## Profile formats

The default output is extended:

~~~bash
pif-gen build --file system.prop --format extended --output-dir output
~~~

Use legacy for consumers that expect the older field set:

~~~bash
pif-gen build --file system.prop --format legacy --output-dir output
~~~

### Extended

The model contains these build fields:

~~~text
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
~~~

It also adds these PIF behavior fields. They are model defaults, not values read from system.prop:

| Field | Default |
|:--|:--:|
| spoofBuild | "1" |
| spoofProps | "1" |
| spoofProvider | "0" |
| spoofSignature | "0" |
| spoofVendingSdk | "0" |
| spoofVendingBuild | "1" |
| verboseLogs | "0" |

DEBUG is true when ro.debuggable=1, or when the resolved build type is userdebug or eng.

### Legacy

The legacy model contains only:

~~~text
MANUFACTURER
MODEL
FINGERPRINT
BRAND
PRODUCT
DEVICE
SECURITY_PATCH
FIRST_API_LEVEL
~~~

## Property selection

For the extended model, each field uses the first non-empty property in this order:

| Field | Property order |
|:--|:--|
| ID | ro.system_ext.build.id, ro.system.build.id, ro.build.id, ro.vendor.build.id, ro.system_dlkm.build.id |
| BRAND | ro.product.system_ext.brand, ro.product.system.brand, ro.product.brand |
| DEVICE | ro.product.system_ext.device, ro.product.system.device, ro.product.device, ro.build.product, ro.product.board |
| MANUFACTURER | ro.product.system_ext.manufacturer, ro.product.system.manufacturer, ro.product.manufacturer |
| MODEL | ro.product.system_ext.model, ro.product.system.model, ro.product.model |
| PRODUCT | ro.product.system_ext.name, ro.product.system.name, ro.product.name, ro.build.product, ro.product.system_ext.device, ro.product.device, ro.product.board |
| FINGERPRINT | ro.system_ext.build.fingerprint, ro.system.build.fingerprint, ro.build.fingerprint, ro.product.build.fingerprint, ro.bootimage.build.fingerprint, ro.vendor.build.fingerprint, ro.system_dlkm.build.fingerprint |
| DEVICE_INITIAL_SDK_INT | ro.product.first_api_level, ro.board.first_api_level, ro.board.api_level, ro.system_ext.build.version.sdk, ro.system.build.version.sdk, ro.build.version.sdk |
| RELEASE | ro.system_ext.build.version.release, ro.system.build.version.release, ro.build.version.release, ro.build.version.release_or_codename |
| TYPE | ro.system_ext.build.type, ro.system.build.type, ro.build.type |
| TAG | ro.system_ext.build.tags, ro.system.build.tags, ro.build.tags |

SECURITY_PATCH checks these direct properties first:

~~~text
ro.build.version.security_patch
ro.vendor.build.security_patch
ro.system.build.version.security_patch
~~~

If none is a 10-character value, the builder extracts a YYMMDD segment from the build ID and then from the fingerprint. For example, BP3A.251005.004 becomes 2025-10-05.

DEBUG is true when ro.debuggable=1, or when the resolved build type is userdebug or eng.

The default values used by the extended builder are:

~~~text
BRAND         google
MANUFACTURER  Google
MODEL         Unknown
TYPE          user
TAG           release-keys
SDK           0
~~~

The SDK value still has to pass validation, so the 0 fallback normally causes an incomplete input to fail rather than produce a profile.

## Validation

Pydantic validates the profile before it is written:

- SECURITY_PATCH must be a real YYYY-MM-DD date.
- DEVICE_INITIAL_SDK_INT and FIRST_API_LEVEL must be numeric strings with a value of at least 21.
- Required string fields cannot be empty.
- A ZIP without system.prop fails.
- In batch mode, each failed asset is logged and the command exits non-zero after processing the list.

## Automation

.github/workflows/generate-pif.yml runs at 02:00 UTC every day and can also be started manually.

The job sequence is:

1. install the package and run pytest tests/;
2. run pif-gen check --state-dir state;
3. build stable and beta assets in parallel when releases changed;
4. validate the JSON files;
5. combine the artifacts into one manifest;
6. publish the daily GitHub release;
7. commit the new state files.

The final state update uses git pull --rebase origin main and pushes to main, so the workflow currently assumes that branch exists.

After the build workflow completes successfully, `.github/workflows/update-latest-index.yml` runs independently. It can also be triggered manually. That workflow finds the newest stable and beta releases separately, generates `releases/latest.json`, validates it, and commits it to the default branch only when the content changes.

## Development

~~~bash
python -m pip install -e '.[dev]'
pytest tests/
~~~

Source files are under src/pif_generator/. The main modules are:

- builder.py : property parsing, ZIP extraction, and profile construction
- models.py : Pydantic models and validators
- pipeline.py : build orchestration and output names
- release.py : GitHub API integration
- cli.py : command-line argument handling
