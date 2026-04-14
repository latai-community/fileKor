"""Adapters for metadata extraction."""
from filekor.adapters.base import MetadataAdapter
from filekor.adapters.exiftool import PyExifToolAdapter

__all__ = ["MetadataAdapter", "PyExifToolAdapter"]