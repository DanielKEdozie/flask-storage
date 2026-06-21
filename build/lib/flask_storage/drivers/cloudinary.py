"""
flask_storage.drivers.cloudinary
---------------------------------
Stores files in Cloudinary.

Required config keys
--------------------
    CLOUD_NAME   Cloudinary cloud name.
    API_KEY      Cloudinary API key.
    API_SECRET   Cloudinary API secret.

Notes
-----
- Cloudinary's ``public_id`` is the UUID stem without the extension.
  The extension is re-appended automatically by Cloudinary on delivery.
- ``delete()`` raises ``StorageNotFoundError`` when Cloudinary returns
  ``{"result": "not found"}`` for consistency with other drivers.
- ``get_url()`` constructs the URL locally — no network call.
"""
from __future__ import annotations

import logging
import os
from typing import IO, Any

from .base import StorageDriver
from ..exceptions import StorageDeleteError, StorageNotFoundError, StorageUploadError
from ..utils import require_keys

log = logging.getLogger(__name__)

_REQUIRED = ('CLOUD_NAME', 'API_KEY', 'API_SECRET')


class CloudinaryDriver(StorageDriver):

    def __init__(self, config: dict[str, Any]) -> None:
        require_keys(config, _REQUIRED, 'cloudinary')
        super().__init__(config)

        import cloudinary              # lazy imports
        import cloudinary.uploader
        import cloudinary.utils

        cloudinary.config(
            cloud_name = config['CLOUD_NAME'],
            api_key    = config['API_KEY'],
            api_secret = config['API_SECRET'],
            secure     = True,
        )
        self._upload  = cloudinary.uploader.upload
        self._destroy = cloudinary.uploader.destroy
        self._cld_url = cloudinary.utils.cloudinary_url

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _public_id(filename: str) -> str:
        """Strip the extension — Cloudinary manages format/version itself."""
        return os.path.splitext(filename)[0]

    # ── Interface ─────────────────────────────────────────────────────────────

    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        public_id = self._public_id(filename)
        try:
            result = self._upload(file_obj, public_id=public_id)
        except Exception as exc:
            raise StorageUploadError(
                f"CloudinaryDriver: upload failed for '{filename}': {exc}"
            ) from exc
        log.debug('CloudinaryDriver uploaded → %s', result['secure_url'])
        return result['secure_url']

    def delete(self, filename: str) -> None:
        public_id = self._public_id(filename)
        try:
            result = self._destroy(public_id)
        except Exception as exc:
            raise StorageDeleteError(
                f"CloudinaryDriver: delete failed for '{public_id}': {exc}"
            ) from exc

        if result.get('result') == 'not found':
            raise StorageNotFoundError(
                f"CloudinaryDriver: asset not found: {public_id}"
            )
        log.debug('CloudinaryDriver deleted → %s', public_id)

    def get_url(self, filename: str) -> str:
        public_id  = self._public_id(filename)
        url, _opts = self._cld_url(public_id, secure=True)
        return url
