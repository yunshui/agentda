"""
Shared test fixtures and configuration for all Agentda tests.

Adds the project root to sys.path so that service modules and logging_lib
are importable from the tests/ directory.
"""

import sys
import importlib.util
from pathlib import Path

# Ensure project root and tests directory are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent
for p in [str(PROJECT_ROOT), str(TESTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import os
import json
import base64
import secrets
import tempfile
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

TOOLS_DIR = PROJECT_ROOT / "tools"


def load_private_key():
    """Load RSA private key from file (duplicated from tools/generate_token_py)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    key_file = TOOLS_DIR / "private_key.pem"
    if key_file.exists():
        with open(key_file, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
    raise FileNotFoundError(f"私钥文件不存在: {key_file}")


def load_public_key():
    """Load RSA public key from file (duplicated from tools/generate_token_py)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    key_file = TOOLS_DIR / "public_key.pem"
    if key_file.exists():
        with open(key_file, "rb") as f:
            return serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )
    raise FileNotFoundError(f"公钥文件不存在: {key_file}")


def import_service_app(service_dir: str, log_dir: str = None):
    """
    Import a FastAPI app from a service directory with hyphen in name.

    Service directories use hyphens (e.g., 'agent-core') which are not valid
    Python identifiers, so we use importlib to load them by file path.

    Uses a temporary log directory to avoid writing to /data/logs/ during tests.
    """
    if log_dir is None:
        log_dir = tempfile.mkdtemp(prefix=f"{service_dir}-")

    main_path = PROJECT_ROOT / service_dir / "main.py"
    spec = importlib.util.spec_from_file_location(
        f"{service_dir.replace('-', '_')}.main",
        main_path
    )
    module = importlib.util.module_from_spec(spec)

    # Add the service directory to sys.path so relative imports work
    service_path = str(PROJECT_ROOT / service_dir)
    if service_path not in sys.path:
        sys.path.insert(0, service_path)

    # Patch log_dir in setup_logging before importing the module
    import logging_lib
    original_setup = logging_lib.setup_logging

    def patched_setup(*args, **kwargs):
        kwargs["log_dir"] = log_dir
        return original_setup(*args, **kwargs)

    with patch.object(logging_lib, "setup_logging", side_effect=patched_setup):
        spec.loader.exec_module(module)

    return module.app

# Test data
TEST_USER_ID = "000000001"
TEST_USER_ID_VIEWER = "000000003"
TEST_USER_ID_ADMIN_BR002 = "000000005"
TEST_USER_ID_INVALID = "123"
TEST_USER_ID_NOT_FOUND = "999999999"


@pytest.fixture(scope="session")
def rsa_private_key():
    """Load the RSA private key for tests."""
    return load_private_key()


@pytest.fixture(scope="session")
def rsa_public_key():
    """Load the RSA public key for tests."""
    return load_public_key()


def _generate_token(user_id: str, token_type: str, expires_delta: timedelta,
                    public_key) -> str:
    """Generate an RSA-encrypted token and return base64-encoded string."""
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes

    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    jti = secrets.token_urlsafe(16)

    token_data = {
        "user_id": user_id,
        "token_type": token_type,
        "jti": jti,
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    plaintext = json.dumps(token_data).encode("utf-8")
    ciphertext = public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return base64.b64encode(ciphertext).decode("utf-8"), token_data


@pytest.fixture(scope="session")
def access_token(rsa_public_key):
    """Generate a valid Access Token for TEST_USER_ID."""
    token, _ = _generate_token(
        TEST_USER_ID, "access", timedelta(minutes=15), rsa_public_key
    )
    return token


@pytest.fixture(scope="session")
def access_token_viewer(rsa_public_key):
    """Generate a valid Access Token for a viewer user."""
    token, _ = _generate_token(
        TEST_USER_ID_VIEWER, "access", timedelta(minutes=15), rsa_public_key
    )
    return token


@pytest.fixture(scope="session")
def access_token_admin_br002(rsa_public_key):
    """Generate a valid Access Token for admin in BR002."""
    token, _ = _generate_token(
        TEST_USER_ID_ADMIN_BR002, "access", timedelta(minutes=15), rsa_public_key
    )
    return token


@pytest.fixture(scope="session")
def expired_access_token(rsa_public_key):
    """Generate an expired Access Token."""
    token, _ = _generate_token(
        TEST_USER_ID, "access", timedelta(minutes=-30), rsa_public_key
    )
    return token


@pytest.fixture(scope="session")
def refresh_token(rsa_public_key):
    """Generate a valid Refresh Token."""
    token, token_data = _generate_token(
        TEST_USER_ID, "refresh", timedelta(days=30), rsa_public_key
    )
    return token, token_data
