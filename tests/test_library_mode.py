# tests/test_library_mode.py

import unittest
import os
from unittest.mock import patch, MagicMock
from kaltura_uploader import KalturaUploader, configure_logging

class TestLibraryMode(unittest.TestCase):
    @patch.object(KalturaUploader, "_get_kaltura_client")
    def test_library_usage_in_script(self, mock_get_client):
        """
        Illustrates how a user might use KalturaUploader in a custom script.
        We patch out network (requests.Session) so no real calls happen.
        """
        os.environ["KALTURA_PARTNER_ID"] = "11111"
        os.environ["KALTURA_ADMIN_SECRET"] = "secret_from_env"

        # Return a mocked client so session.start won't talk to real Kaltura
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Suppose a user writes a script:
        configure_logging(json_file_path="test_lib_mode.log", verbose=True)
        uploader = KalturaUploader(
            partner_id=11111,
            admin_secret="secret_from_env",
            chunk_size_kb=512,
            verbose=True,
            adaptive_chunking=False,
        )

        # We'll also patch out the chunk-upload, so we never call requests.post
        with patch.object(uploader, "_upload_chunk") as mock_upload_chunk, \
            patch("os.path.exists", return_value=True), \
            patch("os.path.isfile", return_value=True), \
            patch("os.path.getsize", return_value=2048), \
            patch("builtins.open", unittest.mock.mock_open(read_data=b"DUMMY_DATA" * 1024)), \
            patch("time.sleep", return_value=None):
            
            # The call will never do real I/O or real network
            mock_upload_token = MagicMock()
            mock_upload_token.id = "fake_token_id"
            mock_client.uploadToken.add.return_value = mock_upload_token
            
            # Also mock out the final status check
            mock_final_token = MagicMock()
            mock_final_token.status = MagicMock(getValue=lambda: 2)  # FULL_UPLOAD=2
            mock_client.uploadToken.get.return_value = mock_final_token

            # Now call the function
            upload_token_id = uploader.upload_file("/tmp/test_file.mov")
            self.assertIsNotNone(upload_token_id)
            self.assertEqual(upload_token_id, "fake_token_id")

            # Optional: verify that `_upload_chunk()` was called at least once
            mock_upload_chunk.assert_called()

if __name__ == "__main__":
    unittest.main()
