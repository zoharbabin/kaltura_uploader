# kaltura_uploader/mime_utils.py

import os
import logging
import mimetypes
from KalturaClient.Plugins.Document import KalturaDocumentType

try:
    import magic  # python-magic (C-based libmagic bindings)
    HAS_PYTHON_MAGIC = True
except ImportError:
    HAS_PYTHON_MAGIC = False
    logging.warning(
        "python-magic is not installed. Falling back to extension-based MIME guess (less reliable)."
    )

def guess_kaltura_entry_type(file_path: str) -> str:
    """
    Determine the Kaltura entry type (media, document, or data) using MIME detection.
    
    1) If python-magic is installed, detect the MIME type by reading the file content (most accurate).
    2) Otherwise, fallback to mimetypes.guess_type() which relies on file extension.
    3) Map known MIME types to:
       - media (image/*, audio/*, video/*)
       - document (application/pdf, application/x-shockwave-flash, application/msword, etc.)
       - data (all else)
    """
    if HAS_PYTHON_MAGIC:
        try:
            # Use python-magic to detect MIME type from file content
            mime_type = magic.from_file(file_path, mime=True)
        except Exception as e:
            logging.warning("python-magic failed to detect MIME type: %s. Falling back to mimetypes.", e)
            mime_type, _ = mimetypes.guess_type(file_path, strict=False)
    else:
        # Fallback to extension-based detection
        mime_type, _ = mimetypes.guess_type(file_path, strict=False)
    
    # Handle the case where MIME detection fails entirely
    if not mime_type:
        logging.debug("Unable to detect MIME type; defaulting to data entry.")
        return "data"

    mime_type = mime_type.lower()
    logging.debug("Detected MIME type: '%s' for file '%s'.", mime_type, file_path)

    # Check major type
    if mime_type.startswith(("image/", "audio/", "video/")):
        return "media"
    elif (
        mime_type == "application/pdf"
        or mime_type == "application/x-shockwave-flash"  # Added mapping for Shockwave Flash
        or mime_type.startswith("application/msword")
        or "application/vnd.openxmlformats-officedocument" in mime_type
    ):
        # This covers PDF, SWF, MS Word, OOXML files
        return "document"
    else:
        # Fallback to a "data" entry for all other MIME types
        return "data"

def get_document_type(mime_type: str) -> int:
    """
    Map MIME type to KalturaDocumentType enumeration value.
    Defaults to KalturaDocumentType.DOCUMENT (11) if MIME type is unrecognized.
    """
    MIME_TO_DOCUMENT_TYPE = {
        'application/pdf': KalturaDocumentType.PDF,  # 13
        'application/x-shockwave-flash': KalturaDocumentType.SWF,  # 12
    }
    return MIME_TO_DOCUMENT_TYPE.get(mime_type, KalturaDocumentType.DOCUMENT)  # 11
