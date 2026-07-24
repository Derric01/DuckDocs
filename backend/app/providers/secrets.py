"""Local secret store for provider API keys (indirect api_key_ref)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


class SecretStore:
    """Encrypts secrets with a machine-local key derived from an env seed or data path.

    Not a hardware keychain, but keeps raw API keys out of provider_configs.json and
    out of routine logs/DB dumps.
    """

    def __init__(self, data_root: Path) -> None:
        self.path = data_root / "secrets.enc.json"
        self._key = self._derive_key(data_root)

    def _derive_key(self, data_root: Path) -> bytes:
        seed = os.getenv("DUCKDOCS_SECRET_SEED") or str(data_root.resolve())
        return hashlib.sha256(seed.encode("utf-8")).digest()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _persist(self, payload: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _xor(self, value: bytes) -> bytes:
        key = self._key
        return bytes(b ^ key[index % len(key)] for index, b in enumerate(value))

    def put(self, secret: str) -> str:
        ref = f"secret:{uuid4().hex}"
        encoded = base64.urlsafe_b64encode(self._xor(secret.encode("utf-8"))).decode("ascii")
        payload = self._load()
        payload[ref] = encoded
        self._persist(payload)
        return ref

    def get(self, ref: str) -> str | None:
        encoded = self._load().get(ref)
        if not encoded:
            return None
        try:
            return self._xor(base64.urlsafe_b64decode(encoded.encode("ascii"))).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    def delete(self, ref: str) -> None:
        payload = self._load()
        if ref in payload:
            del payload[ref]
            self._persist(payload)
