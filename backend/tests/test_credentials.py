"""Credential resolution for the backend's Firestore (Google Cloud) access.

The standard mechanism is the GOOGLE_APPLICATION_CREDENTIALS environment
variable (a path to a Google service-account JSON). These tests prove the
backend reads that variable, fails loudly when the file is missing/unreadable,
and never falls back to a GCE metadata-server probe (which would stall startup
on hosts without one).
"""
from __future__ import annotations

import json
import os

import google.auth
import pytest
from google.auth import environment_vars

from app.credentials import (
    get_credentials,
    get_explicit_credentials_path,
    is_adc_available,
)

_CREDENTIALS_VAR = environment_vars.CREDENTIALS  # GOOGLE_APPLICATION_CREDENTIALS
_CLOUD_SDK_DIR_VAR = environment_vars.CLOUD_SDK_CONFIG_DIR


def _rsa_private_key_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _service_account_json(private_key: str) -> dict:
    return {
        "type": "service_account",
        "project_id": "grounded-test-project",
        "private_key_id": "test-key-id",
        "private_key": private_key,
        "client_email": "grounded-backend@grounded-test-project.iam.gserviceaccount.com",
        "client_id": "1234567890",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/"
        "grounded-backend%40grounded-test-project.iam.gserviceaccount.com",
    }


@pytest.fixture
def service_account_file(tmp_path):
    data = _service_account_json(_rsa_private_key_pem())
    path = tmp_path / "grounded-coffeeshop-ai.json"
    path.write_text(json.dumps(data))
    return path


def test_get_credentials_loads_from_env_path(monkeypatch, service_account_file):
    """GOOGLE_APPLICATION_CREDENTIALS drives the load; no metadata probe."""
    monkeypatch.setenv(_CREDENTIALS_VAR, str(service_account_file))

    def _boom(*args, **kwargs):  # pragma: no cover - assertion guard
        raise AssertionError("google.auth.default must not probe the metadata server")

    monkeypatch.setattr(google.auth, "default", _boom)

    creds = get_credentials()
    assert isinstance(creds, google.auth.credentials.Credentials)
    assert creds.service_account_email.startswith("grounded-backend@")


def test_get_credentials_fails_clearly_when_file_missing(monkeypatch, tmp_path):
    missing = tmp_path / "does-not-exist.json"
    monkeypatch.setenv(_CREDENTIALS_VAR, str(missing))

    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS is set"):
        get_credentials()


def test_get_credentials_fails_clearly_when_path_is_directory(monkeypatch, tmp_path):
    monkeypatch.setenv(_CREDENTIALS_VAR, str(tmp_path))

    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS is set"):
        get_credentials()


def test_get_credentials_fails_clearly_when_file_unreadable(
    monkeypatch, tmp_path, service_account_file
):
    service_account_file.chmod(0)
    monkeypatch.setenv(_CREDENTIALS_VAR, str(service_account_file))
    if os.access(service_account_file, os.R_OK):
        pytest.skip("running as root: unreadable files are still readable")

    with pytest.raises(RuntimeError, match="GOOGLE_APPLICATION_CREDENTIALS is set"):
        get_credentials()


def test_get_credentials_uses_service_account_loader(
    monkeypatch, tmp_path
):
    """A valid path is handed to the service-account loader, not default()."""
    target = tmp_path / "sa.json"
    target.write_text("{}")
    monkeypatch.setenv(_CREDENTIALS_VAR, str(target))

    class _StubCredentials:
        project_id = "grounded-test-project"

    from google.oauth2 import service_account as sa_mod

    monkeypatch.setattr(
        sa_mod.Credentials,
        "from_service_account_file",
        classmethod(lambda cls, filename, scopes=None, **kwargs: _StubCredentials()),
    )

    def _boom(*args, **kwargs):  # pragma: no cover - assertion guard
        raise AssertionError("google.auth.default must not probe the metadata server")

    monkeypatch.setattr(google.auth, "default", _boom)

    creds = get_credentials()
    assert isinstance(creds, _StubCredentials)
    assert creds.project_id == "grounded-test-project"


def test_get_credentials_no_sources_raises_without_probe(monkeypatch, tmp_path):
    monkeypatch.delenv(_CREDENTIALS_VAR, raising=False)
    monkeypatch.setenv(_CLOUD_SDK_DIR_VAR, str(tmp_path))

    def _boom(*args, **kwargs):  # pragma: no cover - assertion guard
        raise AssertionError("google.auth.default must not probe the metadata server")

    monkeypatch.setattr(google.auth, "default", _boom)

    with pytest.raises(RuntimeError, match="No Google Cloud credentials found"):
        get_credentials()


def test_get_credentials_uses_gcloud_adc_file(monkeypatch, tmp_path):
    """Well-known gcloud ADC file is used when the env var is unset."""
    adc_dir = tmp_path / "gcloud"
    adc_dir.mkdir()
    adc = adc_dir / "application_default_credentials.json"
    adc.write_text(json.dumps(_service_account_json(_rsa_private_key_pem())))
    monkeypatch.delenv(_CREDENTIALS_VAR, raising=False)
    monkeypatch.setenv(_CLOUD_SDK_DIR_VAR, str(adc_dir))

    creds = get_credentials()
    assert isinstance(creds, google.auth.credentials.Credentials)


def test_get_explicit_credentials_path_expands_tilde(monkeypatch):
    monkeypatch.setenv(_CREDENTIALS_VAR, "~/somewhere/creds.json")
    assert get_explicit_credentials_path() == os.path.join(
        os.path.expanduser("~"), "somewhere", "creds.json"
    )


def test_get_explicit_credentials_path_none_when_unset(monkeypatch):
    monkeypatch.delenv(_CREDENTIALS_VAR, raising=False)
    assert get_explicit_credentials_path() is None


def test_is_adc_available_true_with_explicit_file(monkeypatch, service_account_file):
    monkeypatch.setenv(_CREDENTIALS_VAR, str(service_account_file))
    assert is_adc_available() is True


def test_is_adc_available_false_without_local_sources(monkeypatch, tmp_path):
    monkeypatch.delenv(_CREDENTIALS_VAR, raising=False)
    monkeypatch.setenv(_CLOUD_SDK_DIR_VAR, str(tmp_path))
    assert is_adc_available() is False