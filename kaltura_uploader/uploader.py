# kaltura_uploader/uploader.py

import os
import time
import logging
import json  
from typing import Optional, TypeVar
import mimetypes
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from KalturaClient import KalturaClient, KalturaConfiguration  # pylint: disable=no-member
from KalturaClient.exceptions import KalturaException
from KalturaClient.Plugins.Core import (  # pylint: disable=no-member
    KalturaSessionType,
    KalturaUploadToken,
    KalturaUploadTokenStatus,
    KalturaCategoryEntry
)
from .constants import KALTURA_SERVICE_URL, KALTURA_API_URL, KALTURA_CDN_URL_TEMPLATE
from .decorators import retry
from .mime_utils import guess_kaltura_entry_type, get_document_type

T = TypeVar("T")

try:
    import magic  # python-magic (C-based libmagic bindings)
    HAS_PYTHON_MAGIC = True
except ImportError:
    HAS_PYTHON_MAGIC = False
    logging.warning(
        "python-magic is not installed. Falling back to extension-based MIME guess (less reliable)."
    )

class TokenNotFinalizedError(Exception):
    """Raised when the Kaltura upload token fails to reach FULL_UPLOAD within the allowed attempts."""

class FileTypeRestrictedError(Exception):
    """Raised when the file type is restricted by Kaltura account settings."""

class KalturaUploader:
    """
    Handles file uploads to Kaltura via chunked uploading with optional adaptive chunk size.
    Creates the appropriate Kaltura entry (Media, Document, or Data) based on file type.

    :param partner_id: Kaltura partner ID.
    :param admin_secret: Kaltura admin secret (keep secure).
    :param chunk_size_kb: Initial chunk size in KB (default ~2MB).
    :param verbose: Enable debug-level logging if True.
    :param adaptive_chunking: If True, dynamically adjust chunk size based on measured speed.
    :param target_upload_time: Target seconds per chunk to guide chunk resizing.
    :param min_chunk_size_kb: Minimum chunk size in KB (adaptive).
    :param max_chunk_size_kb: Maximum chunk size in KB (adaptive).
    :param ks_privileges: Custom privileges to add to the Kaltura Session.
    :param ks_expiry: Kaltura Session expiry time in seconds (default=86400, 24 hours).
    """

    def __init__(
        self,
        partner_id: int,
        admin_secret: str,
        chunk_size_kb: int = 2048,
        verbose: bool = False,
        adaptive_chunking: bool = False,
        target_upload_time: float = 5.0,
        min_chunk_size_kb: int = 1024,
        max_chunk_size_kb: int = 102400,
        ks_privileges: str = None,
        ks_expiry: int = 86400,
    ) -> None:
        if chunk_size_kb < 1:
            raise ValueError("chunk_size_kb must be at least 1 KB")

        self.partner_id = partner_id
        # Keep admin_secret out of logs
        self.admin_secret = admin_secret
        self.ks_privileges = ks_privileges
        self.ks_expiry = ks_expiry

        self.verbose = verbose
        self.adaptive_chunking = adaptive_chunking
        self.target_upload_time = target_upload_time
        self.min_chunk_size_kb = min_chunk_size_kb
        self.max_chunk_size_kb = max_chunk_size_kb

        self.chunk_size_kb = float(chunk_size_kb)
        self.chunk_size_bytes = int(self.chunk_size_kb * 1024)

        self.client = self._get_kaltura_client()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "KalturaStaticFilesUploader/1.0"})

        if self.verbose:
            logging.debug(
                "Initialized KalturaUploader with chunk_size=%.2f KB, adaptive_chunking=%s, "
                "target_upload_time=%.1f s, min_chunk_size_kb=%d, max_chunk_size_kb=%d",
                self.chunk_size_kb,
                self.adaptive_chunking,
                self.target_upload_time,
                self.min_chunk_size_kb,
                self.max_chunk_size_kb
            )

    def _get_kaltura_client(self) -> KalturaClient:
        """
        Creates and returns a KalturaClient with an authenticated admin session (KS).
        """
        config = KalturaConfiguration(self.partner_id)
        config.serviceUrl = KALTURA_SERVICE_URL
        client = KalturaClient(config)
        client.setClientTag("kaltura_cli_file_uploader")  # pylint: disable=no-member

        # Start admin session
        ks = client.session.start(  # pylint: disable=no-member
            self.admin_secret,
            "kaltura_cli_file_uploader",
            KalturaSessionType.ADMIN,
            self.partner_id,
            self.ks_expiry,  # Use the configurable expiry time
            self.ks_privileges
        )
        client.setKs(ks)  # pylint: disable=no-member
        return client

    def _adjust_chunk_size(self, upload_time: float, current_chunk_size_bytes: int) -> None:
        """
        Adjust chunk size based on measured upload time, aiming for target_upload_time.
        Respects min_chunk_size_kb and max_chunk_size_kb.
        """
        if not self.adaptive_chunking or upload_time <= 0:
            return

        current_chunk_kb = current_chunk_size_bytes / 1024.0
        current_speed_kb_s = current_chunk_kb / upload_time
        ideal_chunk_size_kb = current_speed_kb_s * self.target_upload_time

        old_chunk_size_kb = self.chunk_size_kb
        new_chunk_size_kb = (old_chunk_size_kb + ideal_chunk_size_kb) / 2.0
        bounded_chunk_size_kb = max(self.min_chunk_size_kb, min(self.max_chunk_size_kb, new_chunk_size_kb))

        self.chunk_size_kb = bounded_chunk_size_kb
        self.chunk_size_bytes = int(bounded_chunk_size_kb * 1024)

        if self.verbose:
            logging.debug(
                "Adaptive chunking: old=%.2fKB, new=%.2fKB, speed=%.2fKB/s, time=%.2fs",
                old_chunk_size_kb,
                self.chunk_size_kb,
                current_speed_kb_s,
                upload_time,
            )

    def upload_file(self, file_path: str) -> str:
        """
        Upload the file in chunks to Kaltura and return the KalturaUploadToken ID.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' does not exist.")
        if not os.path.isfile(file_path):
            raise ValueError(f"Path '{file_path}' is not a valid file.")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError(f"File '{file_path}' is empty. Aborting upload.")
        if self.verbose:
            logging.debug("File size of '%s' is %d bytes.", file_path, file_size)
        # 1) Create upload token
        upload_token = self._create_upload_token(file_path, file_size)
        offset = 0

        # 2) Chunked upload
        with open(file_path, "rb") as infile:
            while offset < file_size:
                chunk = infile.read(self.chunk_size_bytes)
                if not chunk:  # Reached EOF earlier than expected
                    break
                is_final_chunk = (offset + len(chunk)) >= file_size

                start_time = time.time()
                self._upload_chunk(upload_token.id, chunk, offset, resume=(offset > 0), is_final_chunk=is_final_chunk)
                elapsed = time.time() - start_time

                offset += len(chunk)
                if self.verbose:
                    logging.debug(
                        "Uploaded %d bytes in %.2fs (offset %d/%d, final: %s)",
                        len(chunk), elapsed, offset, file_size, is_final_chunk
                    )

                self._adjust_chunk_size(elapsed, len(chunk))

        # 3) Finalize the upload (only if needed)
        # If we've already uploaded the final chunk, the token might be auto-finalized by the server
        try:
            logging.debug("Attempting to finalize upload token %s after uploading %d/%d bytes",
                         upload_token.id, offset, file_size)
            self._finalize_upload_token(upload_token.id, file_size)
            logging.debug("Successfully finalized upload token %s manually", upload_token.id)
        except KalturaException as e:
            if "UPLOAD_TOKEN_NOT_FOUND" in str(e) and offset >= file_size:
                # This is expected if the server auto-finalized the token after the final chunk
                logging.info("Upload token %s was auto-finalized by the server after final chunk upload", upload_token.id)
                # Set a flag in the log that we can check later
                logging.debug("AUTO_FINALIZED_TOKEN: %s", upload_token.id)
            else:
                # For other errors, or if we didn't upload all chunks, re-raise
                logging.error("Error finalizing token %s: %s", upload_token.id, e)
                raise
        
        return upload_token.id

    def _create_upload_token(self, file_path: str, file_size: int) -> KalturaUploadToken:
        """
        Create a Kaltura upload token for the file to be uploaded.
        """
        token = KalturaUploadToken()
        token.fileName = os.path.basename(file_path)
        token.fileSize = file_size

        if self.verbose:
            logging.debug(
                "Creating upload token for '%s' (%d bytes).", token.fileName, file_size
            )

        # Add detailed logging for token creation
        try:
            result = self.client.uploadToken.add(token)  # pylint: disable=no-member
            logging.debug("Upload token created successfully: %s", result.id)
            # Verify token was created by immediately getting it
            verification = self.client.uploadToken.get(result.id)  # pylint: disable=no-member
            logging.debug("Upload token verified: %s (status: %s)",
                         verification.id, verification.status)
            return result
        except KalturaException as e:
            logging.error("Failed to create upload token: %s", e)
            raise
        except (requests.RequestException, IOError) as e:
            logging.error("Network or I/O error creating upload token: %s", e)
            raise

    @retry((requests.exceptions.RequestException,), max_attempts=5)
    def _upload_chunk(
        self,
        upload_token_id: str,
        chunk: bytes,
        offset: int,
        resume: bool,
        is_final_chunk: bool
    ) -> None:
        """
        Upload a single chunk to Kaltura.
        """
        fields = {
            "resume": "1" if resume else "0",
            "resumeAt": str(offset),
            "finalChunk": "1" if is_final_chunk else "0",
            "fileData": (f"chunk_{offset}", chunk, "application/octet-stream"),
        }
        encoder = MultipartEncoder(fields=fields)
        headers = {"Content-Type": encoder.content_type}
        upload_url = f"{self.client.config.serviceUrl}/api_v3/service/uploadtoken/action/upload"
        params = {
            "uploadTokenId": upload_token_id,
            "ks": self.client.getKs(),   # pylint: disable=no-member
        }

        logging.debug(
            "Uploading chunk: token=%s, offset=%d, size=%d bytes, final=%s",
            upload_token_id, offset, len(chunk), is_final_chunk
        )
        
        try:
            response = self.session.post(
                upload_url,
                headers=headers,
                data=encoder,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            # Log response details
            try:
                resp_data = response.json()
                logging.debug("Chunk upload response: %s", resp_data)
            except ValueError:
                logging.debug("Chunk upload successful (status %d)", response.status_code)
                
        except (requests.RequestException, IOError) as e:
            logging.error("Chunk upload failed due to network or I/O error: %s", e)
            raise
        except ValueError as e:
            logging.error("Chunk upload failed due to value error: %s", e)
            raise

    def _finalize_upload_token(self, upload_token_id: str, file_size: int) -> None:
        """
        Poll until the token is FULL_UPLOAD or fail after several attempts.
        Uses a simple exponential backoff (1s, 2s, 4s, ...)
        """

        max_attempts = 5
        delay = 1.0  # seconds

        # Check if we need to refresh the session
        try:
            # Verify client is still valid by making a simple API call
            partner_info = self.client.partner.get(self.partner_id)  # pylint: disable=no-member
            logging.debug("Partner connection verified: %s", partner_info.name)
        except (KalturaException, requests.RequestException) as e:
            logging.warning("Partner verification failed, refreshing session: %s", e)
            # Refresh the client session
            self.client = self._get_kaltura_client()

        last_exception = None
        for attempt in range(1, max_attempts + 1):
            try:
                logging.debug("Attempt %d/%d: Getting upload token %s",
                             attempt, max_attempts, upload_token_id)
                token = self.client.uploadToken.get(upload_token_id)  # pylint: disable=no-member
                logging.debug("Token retrieved successfully: %s", token.id)
                
                if self._validate_upload_token_status(token, file_size):
                    # If it's FULL_UPLOAD, we're done
                    return

                # Otherwise, if we haven't reached max attempts, sleep and retry
                if attempt < max_attempts:
                    if self.verbose:
                        logging.debug(
                            "Upload token %s is not FULL_UPLOAD on attempt %d/%d; "
                            "waiting %.1fs before next check...",
                            upload_token_id, attempt, max_attempts, delay
                        )
                    time.sleep(delay)
                    delay *= 2.0  # Exponential backoff
            except (KalturaException, requests.RequestException) as e:
                last_exception = e
                logging.error("Error getting upload token on attempt %d/%d: %s",
                             attempt, max_attempts, e)
                if attempt < max_attempts:
                    logging.debug("Retrying after error in %.1fs...", delay)
                    time.sleep(delay)
                    delay *= 2.0  # Exponential backoff
                
        # If we get here, all attempts failed
        if last_exception:
            logging.error("All attempts to finalize token %s failed", upload_token_id)
            raise last_exception

        # If we exhaust all attempts, raise an error
        raise TokenNotFinalizedError(
            f"Upload token {upload_token_id} not finalized after {max_attempts} attempts."
        )

    def _validate_upload_token_status(self, upload_token, file_size: int) -> bool:
        """
        Check if the upload token status is FULL_UPLOAD (completed).
        Returns True if completed, False otherwise.
        """
        status_value = (
            upload_token.status.getValue()
            if hasattr(upload_token.status, "getValue")
            else upload_token.status
        )
        if status_value == KalturaUploadTokenStatus.FULL_UPLOAD:
            logging.info(
                "Upload token %s finalized: %s - %d/%d bytes",
                upload_token.id, upload_token.fileName, upload_token.uploadedFileSize, file_size
            )
            return True

        if self.verbose:
            logging.debug(
                "Current upload token status for %s: %s (not FULL_UPLOAD).",
                upload_token.id, status_value
            )
        return False

    def create_kaltura_entry(
        self,
        upload_token_id: str,
        file_path: str,
        tags: Optional[str] = None,
        access_control_id: Optional[int] = 0,
        conversion_profile_id: Optional[int] = 0
    ) -> str:
        """
        Creates a Kaltura entry (MediaEntry, DocumentEntry, or DataEntry)
        based on the file's extension. Returns the new entry ID.

        :param upload_token_id: The ID of a finalized Kaltura upload token.
        :param file_path: The local file path (used to guess the entry type).
        :param tags: Optional comma-separated tags.
        :param access_control_id: Optional access control ID.
        :param conversion_profile_id: Optional conversion profile ID.
        :return: The Kaltura entry ID.
        
        :raises FileTypeRestrictedError: If the file type is restricted by Kaltura account settings.
        """
        # Check token status first
        token_status_verified = False
        
        try:
            token = self.client.uploadToken.get(upload_token_id)  # pylint: disable=no-member
            status_value = (
                token.status.getValue()
                if hasattr(token.status, "getValue")
                else token.status
            )
            if status_value != KalturaUploadTokenStatus.FULL_UPLOAD:
                raise RuntimeError(f"Upload token {upload_token_id} not finalized (status: {status_value}).")
            token_status_verified = True
        except KalturaException as e:
            # If we get UPLOAD_TOKEN_NOT_FOUND, this might indicate a file type restriction
            if "UPLOAD_TOKEN_NOT_FOUND" in str(e):
                # Get the file extension and MIME type for better error reporting
                file_name = os.path.basename(file_path)
                file_ext = os.path.splitext(file_name)[1].lower()
                
                if HAS_PYTHON_MAGIC:
                    try:
                        mime_type = magic.from_file(file_path, mime=True)
                    except (ImportError, OSError, AttributeError):
                        mime_type, _ = mimetypes.guess_type(file_path, strict=False)
                else:
                    mime_type, _ = mimetypes.guess_type(file_path, strict=False)
                
                logging.error(
                    "Upload token %s not found. This may be due to file type restrictions "
                    "in your Kaltura account settings for file type: %s (%s)",
                    upload_token_id, file_ext, mime_type or "unknown"
                )
                raise FileTypeRestrictedError(
                    f"The file type '{file_ext}' ({mime_type or 'unknown'}) appears to be restricted "
                    f"by your Kaltura account settings. The upload token was automatically deleted. "
                    f"Please check your Kaltura account configuration to allow this file type."
                ) from e
            else:
                logging.error("Unexpected Kaltura error when verifying token %s: %s", upload_token_id, e)
                # For other Kaltura errors, re-raise
                raise
        
        if not token_status_verified:
            # This should not happen, but just in case
            raise RuntimeError(f"Could not verify token status for {upload_token_id}")
            
        # Determine which entry type to create
        entry_type = guess_kaltura_entry_type(file_path)
        file_name = os.path.basename(file_path)
        
        # Get MIME type for mapping
        if HAS_PYTHON_MAGIC:
            try:
                mime_type = magic.from_file(file_path, mime=True)
            except (ImportError, OSError) as e:
                logging.warning("python-magic failed to detect MIME type: %s. Falling back to mimetypes.", e)
                mime_type, _ = mimetypes.guess_type(file_path, strict=False)
        else:
            mime_type, _ = mimetypes.guess_type(file_path, strict=False)
        
        if not mime_type:
            logging.debug("Unable to detect MIME type; defaulting to data entry.")
            mime_type = 'application/octet-stream'  # Default MIME type

        if entry_type == "media":
            entry_id = self._create_media_entry(upload_token_id, file_name, tags, access_control_id, conversion_profile_id)
        elif entry_type == "document":
            entry_id = self._create_document_entry(upload_token_id, file_name, tags, mime_type, access_control_id, conversion_profile_id)
        else:
            # Default fallback: DataEntry
            entry_id = self._create_data_entry(upload_token_id, file_name, tags, access_control_id)

        logging.info("Successfully created Kaltura %s entry: %s", entry_type, entry_id)
        return entry_id

    def _create_media_entry(self, upload_token_id: str, file_name: str, tags: Optional[str], access_control_id: Optional[int] = 0, conversion_profile_id: Optional[int] = 0) -> str:
        """
        Create a KalturaMediaEntry using 'media' service and 'addFromUploadedFile'.
        """
        payload = {
            "service": "media",
            "action": "addFromUploadedFile",
            "mediaEntry:objectType": "KalturaMediaEntry",
            "mediaEntry:name": file_name,
            "mediaEntry:mediaType": 1,  # 1=video, 2=image, 5=audio, etc.
            "uploadTokenId": upload_token_id,
            "ks": self.client.getKs(),  # pylint: disable=no-member
            "format": 1,  # JSON
        }
        if access_control_id > 0:
            payload["mediaEntry:accessControlId"] = access_control_id
        if conversion_profile_id > 0:
            payload["mediaEntry:conversionProfileId"] = conversion_profile_id
        if tags:
            payload["mediaEntry:tags"] = tags

        if self.verbose:
            logging.debug("Creating media entry for '%s' with token '%s'.", file_name, upload_token_id)

        response = self.session.post(KALTURA_API_URL, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "id" not in data:
            raise RuntimeError(f"Unexpected response: {data}")
        return data["id"]

    def _create_document_entry(self, upload_token_id: str, file_name: str, tags: Optional[str], mime_type: str, access_control_id: Optional[int] = 0, conversion_profile_id: Optional[int] = 0) -> str:
        """
        Create a KalturaDocumentEntry using 'document' service and 'addFromUploadedFile'.
        """
        document_type = get_document_type(mime_type)
        
        payload = {
            "service": "document",
            "action": "addFromUploadedFile",
            "documentEntry:objectType": "KalturaDocumentEntry",
            "documentEntry:name": file_name,
            "documentEntry:documentType": document_type,
            "uploadTokenId": upload_token_id,
            "ks": self.client.getKs(),   # pylint: disable=no-member
            "format": 1,
        }
        if access_control_id > 0:
            payload["documentEntry:accessControlId"] = access_control_id
        if conversion_profile_id > 0:
            payload["documentEntry:conversionProfileId"] = conversion_profile_id
        if tags:
            payload["documentEntry:tags"] = tags

        if self.verbose:
            logging.debug("Creating document entry for '%s' with token '%s'.", file_name, upload_token_id)

        response = self.session.post(KALTURA_API_URL, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "id" not in data:
            raise RuntimeError(f"Unexpected response: {data}")
        return data["id"]

    def _create_data_entry(self, upload_token_id: str, file_name: str, tags: Optional[str], access_control_id: Optional[int] = 0) -> str:
        """
        Create a KalturaDataEntry (e.g., for arbitrary file types).
        """
        payload = {
            "service": "baseEntry",
            "action": "addFromUploadedFile",
            "entry:objectType": "KalturaDataEntry",
            "type": 6,  # 6 => KalturaEntryType.DATA
            "entry:name": file_name,
            "entry:conversionProfileId": -1,
            "uploadTokenId": upload_token_id,
            "ks": self.client.getKs(),  # pylint: disable=no-member
            "format": 1,  # JSON
        }
        if access_control_id > 0:
            payload["entry:accessControlId"] = access_control_id
        if tags:
            payload["entry:tags"] = tags

        if self.verbose:
            logging.debug("Creating data entry for '%s' with token '%s'.", file_name, upload_token_id)

        response = self.session.post(KALTURA_API_URL, data=payload, timeout=15)
        response.raise_for_status()
        
        try:
            data = response.json()
            if "id" not in data:
                raise RuntimeError(f"Unexpected response: {data}")
            return data["id"]
        except json.JSONDecodeError as e:
            # Handle the case where the response is not valid JSON
            logging.error("Failed to parse JSON response: %s", e)
            logging.error("Response content: %s", response.text[:1000])
            
            # Provide a more helpful error message
            raise RuntimeError(
                f"Failed to create entry with token {upload_token_id}. "
                f"The server returned an invalid response: {e}. "
                f"This may be due to API limitations or server issues."
            ) from e

    def assign_category(self, entry_id: str, category_id: int) -> None:
        """
        Assign a Kaltura entry to a category if category_id > 0.
        """
        if category_id <= 0:
            return

        cat_entry_params = KalturaCategoryEntry(categoryId=category_id, entryId=entry_id)
        
        try:
            self.client.categoryEntry.add(cat_entry_params)  # pylint: disable=no-member
            logging.info("Assigned entry %s to category %d.", entry_id, category_id)
        except KalturaException as e:
            logging.warning("Failed to assign entry %s to category %d: %s", entry_id, category_id, e)

    def get_direct_serve_url(
        self,
        entry_id: str,
        file_name: str,
        dl_url_extra_params: str = ""
    ) -> str:
        """
        Construct a direct-serve CDN URL for the uploaded file.
        """
        extra_query = f"?{dl_url_extra_params}" if dl_url_extra_params else ""
        url = KALTURA_CDN_URL_TEMPLATE.format(
            partner_id=self.partner_id,
            entry_id=entry_id,
            file_name=file_name,
            extra_query=extra_query
        )
        if self.verbose:
            logging.debug("Generated direct serve URL: %s", url)
        return url
