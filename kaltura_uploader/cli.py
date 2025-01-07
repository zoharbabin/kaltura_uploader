# kaltura_uploader/cli.py

import os
import argparse
import logging
from typing import Optional

from dotenv import load_dotenv  # Import load_dotenv from python-dotenv

from .uploader import KalturaUploader
from .logging_config import configure_logging


def main() -> int:
    """Entry point for the kaltura_uploader CLI."""
    # Load environment variables from .env file
    load_dotenv()  # This reads the .env file and sets the environment variables

    parser = argparse.ArgumentParser(
        description="Upload a file to Kaltura, create the correct entry type (Media/Document/Data), and log results."
    )
    parser.add_argument("file_path", type=str, help="Path to the file to upload.")
    parser.add_argument(
        "--access_control_id", 
        type=int, 
        default=0,
        help="Access control ID to apply on the created entry."
    )
    parser.add_argument(
        "--conversion_profile_id", 
        type=int, 
        default=0,
        help="Conversion Profile ID to apply on the created entry."
    )
    parser.add_argument(
        "--dl_url_extra_params",
        type=str,
        nargs="?",
        default="",
        help="Additional URL parameters, appended as '?...' if non-empty."
    )
    parser.add_argument(
        "--json_log_file",
        type=str,
        default="kaltura_upload.log",
        help="Path to JSON log file (default='kaltura_upload.log')."
    )
    parser.add_argument(
        "--chunk_size",
        type=int,
        default=2048,
        help="Initial chunk size in KB (default=2048 ~ 2MB)."
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable adaptive chunking based on upload speed."
    )
    parser.add_argument(
        "--target_time",
        type=float,
        default=5.0,
        help="Target upload time per chunk in seconds (default=5)."
    )
    parser.add_argument(
        "--min_chunk_size",
        type=int,
        default=1024,
        help="Minimum chunk size in KB when adaptive chunking (default=1024)."
    )
    parser.add_argument(
        "--max_chunk_size",
        type=int,
        default=102400,
        help="Maximum chunk size in KB when adaptive chunking (default=102400)."
    )
    parser.add_argument(
        "--category_id",
        type=int,
        default=0,
        help="Optional category ID to assign to the new entry (skip if <= 0)."
    )
    parser.add_argument(
        "--tags",
        type=str,
        default="",
        help="Optional comma-separated tags to attach to the entry."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging in console."
    )
    parser.add_argument(
        "--partner_id_env",
        type=str,
        default="KALTURA_PARTNER_ID",
        help="Environment variable name for Kaltura partner ID."
    )
    parser.add_argument(
        "--admin_secret_env",
        type=str,
        default="KALTURA_ADMIN_SECRET",
        help="Environment variable name for Kaltura admin secret."
    )

    args = parser.parse_args()

    # Configure logging (color console + JSON file), scrubbing KS from logs
    configure_logging(json_file_path=args.json_log_file, verbose=args.verbose)

    # Fetch from environment variables
    partner_id = os.getenv(args.partner_id_env)
    admin_secret = os.getenv(args.admin_secret_env)

    if not partner_id or not admin_secret:
        logging.error("Missing Kaltura credentials. Please set the environment variables or provide them via arguments.")
        return 1

    # Convert partner_id to integer
    try:
        partner_id = int(partner_id)
    except ValueError:
        logging.error("Invalid Kaltura partner ID. It must be an integer.")
        return 1

    # Check file existence
    if not os.path.exists(args.file_path):
        logging.error("File '%s' does not exist.", args.file_path)
        return 1
    if not os.path.isfile(args.file_path):
        logging.error("Path '%s' is not a valid file.", args.file_path)
        return 1

    # Perform upload and entry creation
    try:
        uploader = KalturaUploader(
            partner_id=partner_id,
            admin_secret=admin_secret,
            chunk_size_kb=args.chunk_size,
            verbose=args.verbose,
            adaptive_chunking=args.adaptive,
            target_upload_time=args.target_time,
            min_chunk_size_kb=args.min_chunk_size,
            max_chunk_size_kb=args.max_chunk_size,
        )

        logging.info("Uploading '%s' to Kaltura...", args.file_path)
        upload_token_id = uploader.upload_file(args.file_path)

        # Determine entry type automatically and create the entry
        entry_id = uploader.create_kaltura_entry(
            upload_token_id,
            file_path=args.file_path,
            tags=args.tags,
            access_control_id=args.access_control_id,
            conversion_profile_id=args.conversion_profile_id
        )

        # Optionally assign category
        if args.category_id > 0:
            uploader.assign_category(entry_id, args.category_id)

        # Generate direct-serve URL
        dl_url = uploader.get_direct_serve_url(
            entry_id, os.path.basename(args.file_path), args.dl_url_extra_params
        )

        logging.info("Successfully uploaded and created entry for '%s'.", args.file_path)
        logging.info("Entry ID: %s", entry_id)
        logging.info("Download URL: %s", dl_url)

        return 0

    except Exception as exc:
        logging.exception("An error occurred during Kaltura upload: %s", exc)
        return 1
