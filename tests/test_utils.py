import unittest
import hashlib
from pathlib import Path

from xscrape.utils import file_hash, sanitize_filename, ensure_dir


class TestUtils(unittest.TestCase):
    def test_file_hash(self):
        content = b"hello world"
        expected = hashlib.md5(content).hexdigest()
        self.assertEqual(file_hash(content), expected)

    def test_sanitize_filename(self):
        invalid_name = "test/file*name:with?invalid<chars>.jpg"
        sanitized = sanitize_filename(invalid_name)
        self.assertEqual(sanitized, "test_file_name_with_invalid_chars_.jpg")

    def test_ensure_dir(self):
        test_dir = Path("test_output_dir")
        if test_dir.exists():
            test_dir.rmdir()
        
        created = ensure_dir(str(test_dir))
        self.assertTrue(created.exists())
        self.assertTrue(created.is_dir())
        
        # cleanup
        test_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
