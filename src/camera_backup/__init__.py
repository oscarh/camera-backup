"""Camera backup system for RTSP cameras to S3-compatible storage."""

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"