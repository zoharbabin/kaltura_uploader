# Kaltura Uploader

**A robust Python CLI tool and library for uploading files to Kaltura with chunked (and adaptive) upload support, automatic MIME type detection, and seamless entry creation for media, documents, and data.**

![GitHub License](https://img.shields.io/badge/license-MIT-green.svg)
![Python Versions](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos-lightgrey)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
  - [Install from PyPI](#install-from-pypi)
  - [Install from Git Clone](#install-from-git-clone)
- [CLI Usage](#cli-usage)
  - [Basic Command](#basic-command)
  - [CLI Arguments and Options](#cli-arguments-and-options)
  - [Common Examples](#common-examples)
  - [Environment Variables](#environment-variables)
- [Using as a Library](#using-as-a-library)
  - [Quick Example](#quick-example)
  - [Advanced Example](#advanced-example)
- [Logging and Security](#logging-and-security)
- [Contributing](#contributing)
- [License](#license)

---

## Features

1. **Chunked Uploading**  
   - Automatically splits files into configurable chunk sizes, reducing the chance of timeouts or large transfer failures.
   - Supports adaptive chunking to dynamically adjust the chunk size based on current upload speed.

2. **Retry Mechanism**  
   - Built-in retries (with exponential backoff) on transient network failures, ensuring more resilient uploads.

3. **Automatic MIME Detection**  
   - Uses [`python-magic`](https://github.com/ahupp/python-magic) if available for accurate MIME detection based on file contents.
   - Falls back to standard extension-based detection if `python-magic` is not installed.

4. **Entry Creation**  
   - Creates the appropriate Kaltura entry type (Media, Document, or Data) based on detected MIME type:
     - **Media**: Video, Audio, or Image
     - **Document**: PDFs, Office docs, SWF, etc.
     - **Data**: All other file types

5. **Direct Download URL**  
   - Automatically constructs a direct serve (CDN) URL for the uploaded entry.

6. **Category Assignment**  
   - Optionally assigns the uploaded file to specific Kaltura categories.

7. **Rich Logging**  
   - Dual-mode logging to console (with optional color via `colorlog`) and JSON files for easy log ingestion.
   - Scrubs sensitive Kaltura session tokens from all logs to prevent accidental leakage.

---

## Installation

The Kaltura Uploader supports **Python 3.10+**. 

### Install from PyPI

The fastest way to get started is to install from [PyPI](https://pypi.org/):

```bash
pip install kaltura-uploader
```

Once installed, you’ll have access to the `kaltura_uploader` CLI.  

### Install from Git Clone

Alternatively, you can clone this repo and install locally:

1. **Clone the Repository**

   ```bash
   git clone https://github.com/zoharbabin/kaltura_uploader.git
   cd kaltura_uploader
   ```

2. **Create a Virtual Environment (recommended)**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install the Package**

   ```bash
   pip install .
   ```

   *or* use editable mode to work on the code while installed:

   ```bash
   pip install -e .
   ```

4. **(Optional) Install Dev/Test Requirements**

   If you plan to run tests or contribute:

   ```bash
   pip install -r requirements.txt
   ```

---

## CLI Usage

After installation, a console command named `kaltura_uploader` becomes available. (If you installed locally in a virtual environment, make sure your environment is activated.)

### Basic Command

```bash
kaltura_uploader /path/to/file.mp4
```

> **Note**: By default, the tool reads Kaltura credentials (`partner_id` and `admin_secret`) from environment variables. See [Environment Variables](#environment-variables) below.

### CLI Arguments and Options

```text
usage: kaltura_uploader [-h] [--access_control_id ACCESS_CONTROL_ID]
                        [--conversion_profile_id CONVERSION_PROFILE_ID]
                        [--dl_url_extra_params DL_URL_EXTRA_PARAMS]
                        [--json_log_file JSON_LOG_FILE]
                        [--chunk_size CHUNK_SIZE]
                        [--adaptive] [--target_time TARGET_TIME]
                        [--min_chunk_size MIN_CHUNK_SIZE]
                        [--max_chunk_size MAX_CHUNK_SIZE]
                        [--category_id CATEGORY_ID] [--tags TAGS]
                        [--verbose]
                        [--partner_id_env PARTNER_ID_ENV]
                        [--admin_secret_env ADMIN_SECRET_ENV]
                        file_path

Upload a file to Kaltura, create the correct entry type (Media/Document/Data),
and log results.

positional arguments:
  file_path             Path to the file to upload.

optional arguments:
  -h, --help            show this help message and exit
  --access_control_id ACCESS_CONTROL_ID
                        Access control ID to apply on the created entry
                        (default=0).
  --conversion_profile_id CONVERSION_PROFILE_ID
                        Conversion profile ID to apply on the created entry
                        (default=0).
  --dl_url_extra_params DL_URL_EXTRA_PARAMS
                        Additional URL parameters appended as '?...' if non-empty.
  --json_log_file JSON_LOG_FILE
                        Path to JSON log file (default=`kaltura_upload.log`).
  --chunk_size CHUNK_SIZE
                        Initial chunk size in KB (default=2048, ~2MB).
  --adaptive            Enable adaptive chunking based on upload speed.
  --target_time TARGET_TIME
                        Target upload time per chunk in seconds (default=5).
  --min_chunk_size MIN_CHUNK_SIZE
                        Minimum chunk size in KB when adaptive chunking (default=1024).
  --max_chunk_size MAX_CHUNK_SIZE
                        Maximum chunk size in KB when adaptive chunking (default=102400).
  --category_id CATEGORY_ID
                        Assign the entry to this Kaltura category if > 0.
  --tags TAGS           Comma-separated tags to attach to the entry.
  --verbose             Enable verbose (DEBUG) logging in console.
  --partner_id_env PARTNER_ID_ENV
                        Name of environment variable containing Kaltura partner ID
                        (default=KALTURA_PARTNER_ID).
  --admin_secret_env ADMIN_SECRET_ENV
                        Name of environment variable containing Kaltura admin secret
                        (default=KALTURA_ADMIN_SECRET).
```

### Common Examples

1. **Minimal CLI Usage**  
   ```bash
   export KALTURA_PARTNER_ID="12345"
   export KALTURA_ADMIN_SECRET="my_admin_secret"

   kaltura_uploader /path/to/video.mp4
   ```
   - Uploads `video.mp4`, uses chunk size of ~2MB, defaults to media entry type if MIME is recognized as video.

2. **Specifying Category and Tags**  
   ```bash
   kaltura_uploader /path/to/presentation.pdf \
       --category_id 678 \
       --tags "presentation,slides"
   ```
   - Uploads `presentation.pdf`, recognized as `document` type.  
   - Automatically assigns it to category 678 and adds tags `presentation,slides`.

3. **Adaptive Chunking**  
   ```bash
   kaltura_uploader /path/to/big_video.mov --adaptive --target_time 10
   ```
   - Starts with a 2MB chunk size, but adjusts automatically per chunk to aim for a 10-second upload time each chunk.

4. **Saving Logs to a Custom File**  
   ```bash
   kaltura_uploader /path/to/my_file.mp4 \
       --json_log_file /var/log/kaltura/kaltura_upload.json
   ```
   - Writes logs in JSON format to `/var/log/kaltura/kaltura_upload.json`.  
   - Console logs are colored (if `colorlog` is installed).

5. **Override Default Environment Variable Names**  
   ```bash
   export MY_PARTNER_ID="55555"
   export MY_ADMIN_SECRET="some_secret_here"

   kaltura_uploader /path/to/image.jpg \
       --partner_id_env MY_PARTNER_ID \
       --admin_secret_env MY_ADMIN_SECRET
   ```
   - Reads credentials from `MY_PARTNER_ID` and `MY_ADMIN_SECRET` instead of the default `KALTURA_PARTNER_ID` / `KALTURA_ADMIN_SECRET`.

### Environment Variables

By default, `kaltura_uploader` looks for two environment variables:

- `KALTURA_PARTNER_ID`: The numeric Kaltura **partner ID**.
- `KALTURA_ADMIN_SECRET`: The **admin secret** associated with that partner ID.

You can also store them in a `.env` file (supported by [python-dotenv](https://pypi.org/project/python-dotenv/)):

```bash
# .env file in your project
KALTURA_PARTNER_ID=12345
KALTURA_ADMIN_SECRET=my_admin_secret
```

Then simply run:

```bash
kaltura_uploader /path/to/video.mp4
```

The tool will load these automatically at runtime.

---

## Using as a Library

In addition to the CLI, `kaltura_uploader` can be imported into Python scripts to programmatically upload files, create entries, and retrieve direct-serve URLs.

### Quick Example

```python
from kaltura_uploader import KalturaUploader

# Provide credentials (commonly from env variables).
partner_id = 12345
admin_secret = "my_admin_secret"

# Initialize the uploader
uploader = KalturaUploader(
    partner_id=partner_id,
    admin_secret=admin_secret,
    chunk_size_kb=2048,        # ~2MB
    verbose=True,              # Enable debug logging
    adaptive_chunking=False,   # Disable or enable adaptive chunking
)

# Upload a file and get the Kaltura upload token
upload_token_id = uploader.upload_file("/path/to/video.mp4")

# Create an entry in Kaltura (automatically determines if it's media/doc/data)
entry_id = uploader.create_kaltura_entry(
    upload_token_id,
    file_path="/path/to/video.mp4",
    tags="example,video",
    access_control_id=0,       # Could be any valid ID if needed
    conversion_profile_id=0,
)

# Optionally assign category
uploader.assign_category(entry_id, 678)

# Get the direct download (CDN) URL
dl_url = uploader.get_direct_serve_url(entry_id, "video.mp4")
print("Entry ID:", entry_id)
print("Direct Download URL:", dl_url)
```

### Advanced Example

```python
import os
from kaltura_uploader import KalturaUploader, configure_logging

# Suppose you store your credentials in environment variables or .env
partner_id = int(os.getenv("KALTURA_PARTNER_ID", "12345"))
admin_secret = os.getenv("KALTURA_ADMIN_SECRET", "some_secret")

# Optionally configure logging with a custom JSON file path
configure_logging(json_file_path="kaltura_upload.log", verbose=True)

# Initialize an uploader with adaptive chunking
uploader = KalturaUploader(
    partner_id=partner_id,
    admin_secret=admin_secret,
    chunk_size_kb=1024,
    verbose=True,
    adaptive_chunking=True,
    target_upload_time=10,
    min_chunk_size_kb=1024,    # 1MB
    max_chunk_size_kb=204800,  # 200MB
)

# Upload, create an entry, and assign category
try:
    file_path = "/path/to/very_large_video.mov"
    token_id = uploader.upload_file(file_path)
    entry_id = uploader.create_kaltura_entry(
        token_id,
        file_path,
        tags="large,upload,example",
        access_control_id=10,
        conversion_profile_id=999
    )
    uploader.assign_category(entry_id, 777)

    direct_url = uploader.get_direct_serve_url(entry_id, os.path.basename(file_path))
    print(f"Successfully uploaded! Entry ID: {entry_id}\nDirect URL: {direct_url}")
except Exception as e:
    print(f"An error occurred: {e}")
```

---

## Logging and Security

1. **Dual Logging**  
   - Writes human-readable logs to the console (with optional coloring via `colorlog`) and JSON logs to a specified file (defaults to `kaltura_upload.log`).

2. **Scrubbing Kaltura Sessions**  
   - The API admin secret is excluded from the log.  
   - The Kaltura session token (`ks`) is automatically replaced with `ks=<REDACTED>` in all log messages to prevent accidental credential leakage.

---

## Contributing

We welcome all contributions, including:

- **Bug Reports**: [Open an issue](https://github.com/zoharbabin/kaltura_uploader/issues) if you find a bug or want to request an enhancement.
- **Pull Requests**: If you want to add features or fix bugs, fork the repository and open a PR. We’ll review and help merge your changes.
- **Discussions**: Feel free to start or join a discussion to brainstorm ideas or get help.

**Steps for contributing**:
1. Fork and clone the repository.
2. Create a new branch for your feature or bug fix.
3. Write tests for your changes in the `tests/` directory.
4. Ensure `pytest` or `unittest` passes all tests.
5. Commit and push your changes to GitHub.
6. Open a pull request against the `main` branch.

---

## License

This project is licensed under the [MIT License](LICENSE).  
You are free to use, modify, and distribute this software in accordance with the MIT license terms.
