"""Test-only environment defaults, applied before Django reads its settings."""
import os

os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
