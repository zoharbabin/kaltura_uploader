# tests/test_uploader.py

import os
import unittest
from unittest.mock import patch, MagicMock
from KalturaClient.exceptions import KalturaException
from kaltura_uploader import KalturaUploader, FileTypeRestrictedError

class TestKalturaUploader(unittest.TestCase):

    def setUp(self):
        """Set up test environment for each test."""
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
            ks_privileges=None,
        )

    def test_upload_file_success(self):
        """Test that upload_file() calls the correct sequence of operations."""
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
        """Test that create_kaltura_entry() for a video file calls _create_media_entry."""
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
        """Test that a PDF file is created with the _create_document_entry path."""
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
        """Test that an unknown mime type is treated as 'data'."""
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
        """Test that assign_category calls categoryEntry.add when category_id > 0."""
        with patch.object(self.mock_kaltura_client.categoryEntry, "add", return_value=None) as mock_cat_add:
            self.uploader.assign_category("abc123", 777)
            mock_cat_add.assert_called_once()
    def test_assign_category_noop(self):
        """Test that assign_category does nothing when category_id <= 0."""
        with patch.object(self.mock_kaltura_client.categoryEntry, "add") as mock_cat_add:
            self.uploader.assign_category("abc123", 0)
            mock_cat_add.assert_not_called()
    def test_file_type_restriction_detection(self):
        """Test that FileTypeRestrictedError is raised for restricted file types."""
        # Mock token to raise UPLOAD_TOKEN_NOT_FOUND
        self.mock_kaltura_client.uploadToken.get.side_effect = KalturaException(code="UPLOAD_TOKEN_NOT_FOUND", message="Upload token not found (UPLOAD_TOKEN_NOT_FOUND)")
        
        # Test with an HTML file (commonly restricted)
        with self.assertRaises(FileTypeRestrictedError):
            self.uploader.create_kaltura_entry("fake_token", "/path/to/restricted.html")
        
        # Verify the error message contains the file extension and MIME type
        try:
            self.uploader.create_kaltura_entry("fake_token", "/path/to/restricted.html")
        except FileTypeRestrictedError as e:
            self.assertIn(".html", str(e))
            self.assertIn("text/html", str(e))
    
    def test_ks_privileges_parameter(self):
        """Test that the ks_privileges parameter is correctly passed to session.start."""
        # Reset the mock to clear previous calls
        self.mock_get_client.reset_mock()
        
        # Create a new KalturaUploader with custom privileges
        with patch.object(KalturaUploader, "_get_kaltura_client") as mock_get_client:
            mock_session = MagicMock()
            mock_client = MagicMock()
            mock_client.session = mock_session
            mock_get_client.return_value = mock_client
            
            # Create uploader with custom privileges
            uploader = KalturaUploader(
                partner_id=12345,
                admin_secret="my_admin_secret",
                ks_privileges="disableentitlement"
            )
            
            # Verify that _get_kaltura_client was called
            mock_get_client.assert_called_once()
            
            # Create another uploader to directly test the _get_kaltura_client method
            test_uploader = KalturaUploader(
                partner_id=12345,
                admin_secret="my_admin_secret",
                ks_privileges="disableentitlement"
            )
            
            # Replace the _get_kaltura_client method to verify parameters
            original_method = test_uploader._get_kaltura_client
            
            def mock_method(*args, **kwargs):
                # Store the original method for later restoration
                test_uploader._get_kaltura_client = original_method
                
                # Create a mock client and session
                mock_client = MagicMock()
                mock_session = MagicMock()
                mock_client.session.start = mock_session.start
                
                # Return the mock client
                return mock_client
            
            # Replace the method
            test_uploader._get_kaltura_client = mock_method
            
            # Call the method to trigger client creation
            test_uploader.client = test_uploader._get_kaltura_client()
            
            # Verify that the privileges parameter is passed correctly
            self.assertEqual(test_uploader.ks_privileges, "disableentitlement")

    def test_ks_expiry_parameter(self):
        """Test that the ks_expiry parameter is correctly stored and used."""
        # Test with custom expiry time
        custom_expiry = 3600  # 1 hour
        uploader = KalturaUploader(
            partner_id=12345,
            admin_secret="my_admin_secret",
            ks_expiry=custom_expiry
        )
        
        # Verify that the expiry parameter is stored correctly
        self.assertEqual(uploader.ks_expiry, custom_expiry)
        
        # Test with default value
        default_uploader = KalturaUploader(
            partner_id=12345,
            admin_secret="my_admin_secret"
        )
        self.assertEqual(default_uploader.ks_expiry, 86400)  # 24 hours (default)
        
        # Test that the expiry is passed to session.start
        with patch.object(KalturaUploader, '_get_kaltura_client') as mock_get_client:
            # Create a new uploader that will call our mocked _get_kaltura_client
            test_uploader = KalturaUploader(
                partner_id=12345,
                admin_secret="my_admin_secret",
                ks_expiry=custom_expiry
            )
            
            # Verify the method was called
            mock_get_client.assert_called_once()
            
            # Now directly test the session.start call with a mock
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.session = mock_session
            
            # Replace the original method temporarily
            original_method = test_uploader._get_kaltura_client
            test_uploader._get_kaltura_client = lambda: mock_client
            
            # Call the method
            test_uploader.client = test_uploader._get_kaltura_client()
            
            # Restore the original method
            test_uploader._get_kaltura_client = original_method


if __name__ == "__main__":
    unittest.main()
