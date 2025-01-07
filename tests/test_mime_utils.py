# tests/test_mime_utils.py

import unittest
from unittest.mock import patch
import mimetypes  # Import mimetypes to prevent NameError in side_effect

from kaltura_uploader.mime_utils import guess_kaltura_entry_type, get_document_type
from KalturaClient.Plugins.Document import KalturaDocumentType

class TestMimeUtils(unittest.TestCase):
    @patch('kaltura_uploader.mime_utils.magic.from_file')
    def test_guess_kaltura_entry_type_document(self, mock_magic):
        """
        Test that 'document.pdf' and 'presentation.swf' are correctly identified as 'document'.
        """
        # Define the side effect function for magic.from_file
        def side_effect(file_path, mime=True):
            if file_path == "document.pdf":
                return "application/pdf"
            elif file_path == "presentation.swf":
                return "application/x-shockwave-flash"
            else:
                return mimetypes.guess_type(file_path)[0]
        
        # Assign the side effect to the mock
        mock_magic.side_effect = side_effect

        # Test 'document.pdf'
        self.assertEqual(guess_kaltura_entry_type("document.pdf"), "document")

        # Test 'presentation.swf'
        self.assertEqual(guess_kaltura_entry_type("presentation.swf"), "document")

    @patch('kaltura_uploader.mime_utils.magic.from_file')
    def test_guess_kaltura_entry_type_media(self, mock_magic):
        """
        Test that media files are correctly identified as 'media'.
        """
        def side_effect(file_path, mime=True):
            if file_path == "video.mp4":
                return "video/mp4"
            elif file_path == "image.jpg":
                return "image/jpeg"
            else:
                return mimetypes.guess_type(file_path)[0]
        
        mock_magic.side_effect = side_effect

        self.assertEqual(guess_kaltura_entry_type("video.mp4"), "media")
        self.assertEqual(guess_kaltura_entry_type("image.jpg"), "media")

    @patch('kaltura_uploader.mime_utils.magic.from_file')
    def test_guess_kaltura_entry_type_data(self, mock_magic):
        """
        Test that data files are correctly identified as 'data'.
        """
        def side_effect(file_path, mime=True):
            if file_path == "script.js":
                return "application/javascript"
            elif file_path == "styles.css":
                return "text/css"
            elif file_path == "archive.zip":
                return "application/java-archive"
            else:
                return mimetypes.guess_type(file_path)[0]
        
        mock_magic.side_effect = side_effect

        self.assertEqual(guess_kaltura_entry_type("script.js"), "data")
        self.assertEqual(guess_kaltura_entry_type("styles.css"), "data")
        self.assertEqual(guess_kaltura_entry_type("archive.zip"), "data")

    def test_get_document_type(self):
        """
        Test the mapping from MIME types to KalturaDocumentType enumeration.
        """
        self.assertEqual(get_document_type("application/pdf"), KalturaDocumentType.PDF)
        self.assertEqual(get_document_type("application/x-shockwave-flash"), KalturaDocumentType.SWF)
        self.assertEqual(get_document_type("application/javascript"), KalturaDocumentType.DOCUMENT)  # Defaults to DOCUMENT
        self.assertEqual(get_document_type("text/css"), KalturaDocumentType.DOCUMENT)  # Defaults to DOCUMENT

if __name__ == "__main__":
    unittest.main()
