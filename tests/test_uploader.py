# tests/test_uploader.py

import os
import unittest
from unittest.mock import patch, MagicMock
from kaltura_uploader import KalturaUploader

class TestKalturaUploader(unittest.TestCase):

    def setUp(self):
        """
        Common setup for each test: 
          - Mock environment variables
          - Create a KalturaUploader instance
        """
        os.environ["KALTURA_PARTNER_ID"] = "12345"
        os.environ["KALTURA_ADMIN_SECRET"] = "my_admin_secret"

        # We'll patch out the `_get_kaltura_client` method so it doesn't
        # actually open a Kaltura session
        patcher = patch.object(KalturaUploader, "_get_kaltura_client")
        self.mock_get_client = patcher.start()
        self.addCleanup(patcher.stop)

        # Provide a MagicMock as our 'client'
        self.mock_kaltura_client = MagicMock()
        self.mock_get_client.return_value = self.mock_kaltura_client

        # Now create the KalturaUploader under test
        self.uploader = KalturaUploader(
            partner_id=12345,
            admin_secret="my_admin_secret",
            chunk_size_kb=1024,
            verbose=True,
        )

    def test_upload_file_success(self):
        """
        Test that upload_file() calls the correct sequence:
          1. Create upload token
          2. Upload chunks
          3. Finalize
        """
        # Mock the file existence
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getsize", return_value=4096), \
             patch("builtins.open", unittest.mock.mock_open(read_data=b"TEST" * 1024)), \
             patch.object(KalturaUploader, "_get_kaltura_client") as mock_get_client, \
             patch.object(KalturaUploader, "_upload_chunk") as mock_upload_chunk:

            # Mock the client.uploadToken.add() return
            mock_upload_token = MagicMock()
            mock_upload_token.id = "fake_token_id"
            self.mock_kaltura_client.uploadToken.add.return_value = mock_upload_token

            # Mock the final status check
            # The code calls self.client.uploadToken.get() repeatedly
            # We'll just return a token with status=KalturaUploadTokenStatus.FULL_UPLOAD
            mock_final_token = MagicMock()
            mock_final_token.status = MagicMock(getValue=lambda: 2)  # FULL_UPLOAD=2
            self.mock_kaltura_client.uploadToken.get.return_value = mock_final_token

            # Actually call upload_file
            token_id = self.uploader.upload_file("/fake/path/to/file.mp4")

            self.assertEqual(token_id, "fake_token_id")
            self.mock_kaltura_client.uploadToken.add.assert_called_once()
            self.mock_kaltura_client.uploadToken.get.assert_called()  # called to finalize

    def test_create_kaltura_entry_media(self):
        """
        Test that create_kaltura_entry() for a 'video.mp4' ends up 
        calling _create_media_entry with the expected payload.
        """
        # We'll patch guess_kaltura_entry_type to return 'media'
        with patch("kaltura_uploader.uploader.guess_kaltura_entry_type", return_value="media"):
            # Make sure the token is in FULL_UPLOAD so the code doesn't raise
            mock_final_token = MagicMock()
            mock_final_token.status = MagicMock(getValue=lambda: 2)  # FULL_UPLOAD=2
            self.mock_kaltura_client.uploadToken.get.return_value = mock_final_token

            # We'll also mock out _create_media_entry so we can check if it was called
            with patch.object(self.uploader, "_create_media_entry", return_value="new_entry_id") as mock_media_entry:
                entry_id = self.uploader.create_kaltura_entry(
                    upload_token_id="fake_token_id",
                    file_path="/fake/path/video.mp4",
                    tags="tag1,tag2",
                    access_control_id=777
                )

                self.assertEqual(entry_id, "new_entry_id")
                mock_media_entry.assert_called_once_with(
                    "fake_token_id",
                    "video.mp4",     # basename of the file
                    "tag1,tag2",
                    777,            # access_control_id
                    0  # default conversion_profile_id
                )

    def test_create_kaltura_entry_document(self):
        """
        Test that a 'document.pdf' is created with the _create_document_entry path.
        """
        with patch("kaltura_uploader.uploader.guess_kaltura_entry_type", return_value="document"):
            # Mock token to FULL_UPLOAD
            mock_final_token = MagicMock()
            mock_final_token.status = MagicMock(getValue=lambda: 2)
            self.mock_kaltura_client.uploadToken.get.return_value = mock_final_token

            with patch.object(self.uploader, "_create_document_entry", return_value="doc_entry_id") as mock_doc_entry:
                entry_id = self.uploader.create_kaltura_entry(
                    "fake_token", "/fake/path/document.pdf", tags="someTag", conversion_profile_id=999
                )
                self.assertEqual(entry_id, "doc_entry_id")
                mock_doc_entry.assert_called_once()

    def test_create_kaltura_entry_data(self):
        """
        Test that an unknown mime type is treated as 'data'.
        """
        with patch("kaltura_uploader.uploader.guess_kaltura_entry_type", return_value="data"):
            # Mock token
            mock_final_token = MagicMock()
            mock_final_token.status = MagicMock(getValue=lambda: 2)
            self.mock_kaltura_client.uploadToken.get.return_value = mock_final_token

            with patch.object(self.uploader, "_create_data_entry", return_value="data_entry_id") as mock_data_entry:
                entry_id = self.uploader.create_kaltura_entry("fake_token", "/unknown/file.xyz")
                self.assertEqual(entry_id, "data_entry_id")
                mock_data_entry.assert_called_once()

    def test_assign_category_success(self):
        """
        Test that assign_category calls self.client.categoryEntry.add(...) 
        if category_id > 0
        """
        with patch.object(self.mock_kaltura_client.categoryEntry, "add", return_value=None) as mock_cat_add:
            self.uploader.assign_category("abc123", 777)
            mock_cat_add.assert_called_once()
    
    def test_assign_category_noop(self):
        """
        If category_id <= 0, we do nothing.
        """
        with patch.object(self.mock_kaltura_client.categoryEntry, "add") as mock_cat_add:
            self.uploader.assign_category("abc123", 0)
            mock_cat_add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
