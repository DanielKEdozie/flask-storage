"""
flask_storage.drivers.gcs
-------------------------
Stores files in Google Cloud Storage.

Required config keys
--------------------
    PROJECT_ID   GCP project ID.
    BUCKET_NAME  Target bucket name.

Optional config keys
--------------------
    URL   CDN base URL override.  When absent the canonical GCS public URL
          is constructed from the bucket name — no network call required.
"""
from __future__ import annotations

import logging
from typing import IO, Any

from .base import StorageDriver
from ..exceptions import StorageDeleteError, StorageNotFoundError, StorageUploadError
from ..utils import require_keys

log = logging.getLogger(__name__)

_REQUIRED = ('PROJECT_ID', 'BUCKET_NAME')


class GCSDriver(StorageDriver):

    def __init__(self, config: dict[str, Any]) -> None:
        require_keys(config, _REQUIRED, 'gcs')
        super().__init__(config)

        from google.cloud import storage as gcs  # lazy import

        client            = gcs.Client(project=config['PROJECT_ID'])
        self._bucket      = client.bucket(config['BUCKET_NAME'])
        self._bucket_name = config['BUCKET_NAME']

    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        try:
            self._bucket.blob(filename).upload_from_file(file_obj)
        except Exception as exc:
            raise StorageUploadError(
                f"GCSDriver: upload failed for '{filename}': {exc}"
            ) from exc
        log.debug('GCSDriver uploaded → gs://%s/%s', self._bucket_name, filename)
        return self.get_url(filename)

    def delete(self, filename: str) -> None:
        blob = self._bucket.blob(filename)
        if not blob.exists():
            raise StorageNotFoundError(
                f"GCSDriver: object not found: gs://{self._bucket_name}/{filename}"
            )
        try:
            blob.delete()
        except Exception as exc:
            raise StorageDeleteError(
                f"GCSDriver: delete failed for '{filename}': {exc}"
            ) from exc
        log.debug('GCSDriver deleted → gs://%s/%s', self._bucket_name, filename)

    def get_url(self, filename: str) -> str:
        if cdn := self.config.get('URL'):
            return f"{cdn.rstrip('/')}/{filename}"
        return f"https://storage.googleapis.com/{self._bucket_name}/{filename}"
