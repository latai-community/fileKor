"""Tests for core/hasher.py — SHA256 helpers."""

from pathlib import Path

import pytest

from filekor.core.hasher import (
    calculate_sha256,
    calculate_sha256_from_bytes,
    calculate_sha256_from_file,
)


class TestCalculateSha256:
    def test_real_file(self, tmp_path):
        """SHA256 of a real file matches hashlib."""
        file_path = tmp_path / "test.txt"
        content = b"hello world"
        file_path.write_bytes(content)

        result = calculate_sha256(str(file_path))
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

        assert result == expected

    def test_empty_file(self, tmp_path):
        """SHA256 of an empty file is the empty hash."""
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")

        result = calculate_sha256(str(file_path))
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        assert result == expected

    def test_large_file(self, tmp_path):
        """SHA256 handles a file larger than the chunk size (8192)."""
        file_path = tmp_path / "large.bin"
        content = b"x" * (8192 * 3 + 123)  # Multiple chunks + remainder
        file_path.write_bytes(content)

        result = calculate_sha256(str(file_path))
        import hashlib

        expected = hashlib.sha256(content).hexdigest()

        assert result == expected


class TestCalculateSha256FromBytes:
    def test_basic(self):
        """Hash from bytes matches expected digest."""
        data = b"pytest rocks"
        result = calculate_sha256_from_bytes(data)
        import hashlib

        expected = hashlib.sha256(data).hexdigest()

        assert result == expected

    def test_empty(self):
        """Hash of empty bytes is the empty SHA256."""
        result = calculate_sha256_from_bytes(b"")
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        assert result == expected


class TestCalculateSha256FromFile:
    def test_with_path_object(self, tmp_path):
        """calculate_sha256_from_file accepts a Path object."""
        file_path = tmp_path / "data.bin"
        content = b"\x00\x01\x02\x03"
        file_path.write_bytes(content)

        result = calculate_sha256_from_file(file_path)
        import hashlib

        expected = hashlib.sha256(content).hexdigest()

        assert result == expected
