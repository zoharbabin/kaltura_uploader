# Kaltura Uploader

A Python CLI tool to upload files to Kaltura, create appropriate entries (Media/Document/Data), and manage logging.

## Features

- **Chunked Uploading**: Handles large files by uploading in chunks with optional adaptive chunk sizing based on upload speed.
- **Retry Mechanism**: Implements retries with exponential backoff for transient errors.
- **Logging**: Dual logging setup with colored console output and JSON-formatted log files. Sensitive information like Kaltura session tokens are scrubbed.
- **MIME Type Detection**: Determines the appropriate Kaltura entry type based on file MIME type, using `python-magic` for accurate detection.
- **Category Assignment**: Optionally assigns uploaded entries to specified categories.
- **Direct Serve URL**: Generates direct download URLs for uploaded files.

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/kaltura_uploader.git
   cd kaltura_uploader
   ```

2. **Create a Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   **Note:** Ensure that the `KalturaClient` library is available. If it's a custom library, you might need to install it separately.

## Usage

```bash
python cli.py partner_id admin_secret file_path access_control_id [dl_url_extra_params] [options]
```

### Arguments

- `partner_id`: Kaltura partner ID.
- `admin_secret`: Kaltura admin secret.
- `file_path`: Path to the file to upload.
- `access_control_id`: Access control ID (currently not used).
- `dl_url_extra_params`: (Optional) Additional URL parameters, appended as `?` if provided.

### Options

- `--json_log_file`: Path to JSON log file (default=`kaltura_upload.log`).
- `--chunk_size`: Initial chunk size in KB (default=2048 ~ 2MB).
- `--adaptive`: Enable adaptive chunking based on upload speed.
- `--target_time`: Target upload time per chunk in seconds (default=5).
- `--min_chunk_size`: Minimum chunk size in KB when adaptive chunking (default=1024).
- `--max_chunk_size`: Maximum chunk size in KB when adaptive chunking (default=102400).
- `--category_id`: Optional category ID to assign to the new entry (skip if <= 0).
- `--tags`: Optional comma-separated tags to attach to the entry.
- `--verbose`: Enable verbose (debug) logging in console.

### Example

```bash
python cli.py 12345 my_admin_secret /path/to/file.mp4 0 --category_id 678 --tags "video,upload" --verbose
```

## Security Considerations

- **Admin Secret**: Ensure that your Kaltura `admin_secret` is kept secure and not exposed in logs or version control systems.
- **Logging**: The tool scrubs sensitive information like Kaltura session tokens from logs to prevent leakage.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

[MIT License](LICENSE)