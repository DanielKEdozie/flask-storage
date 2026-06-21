"""
flask_storage.drivers.local
---------------------------
Stores files on the local filesystem.

Required config keys
--------------------
    PATH   Absolute path to the upload directory.
    URL    Public base URL, e.g. ``http://localhost:5000/uploads/``.
"""
from __future__ import annotations

import logging
import os
from typing import IO, Any

from .base import StorageDriver
from ..exceptions import (
    StorageConfigError,
    StorageDeleteError,
    StorageNotFoundError,
    StorageUploadError,
)
from ..utils import require_keys

log = logging.getLogger(__name__)

_REQUIRED = ('PATH', 'URL')


class LocalDriver(StorageDriver):

    def __init__(self, config: dict[str, Any]) -> None:
        require_keys(config, _REQUIRED, 'local')
        super().__init__(config)
        try:
            os.makedirs(config['PATH'], exist_ok=True)
        except OSError as exc:
            raise StorageConfigError(
                f"LocalDriver: cannot create upload directory "
                f"'{config['PATH']}': {exc}"
            ) from exc

    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        path = os.path.join(self.config['PATH'], filename)
        try:
            if hasattr(file_obj, 'save'):
                file_obj.save(path)          # Werkzeug FileStorage
            else:
                with open(path, 'wb') as fh:
                    fh.write(file_obj.read())
        except OSError as exc:
            raise StorageUploadError(
                f"LocalDriver: write failed for '{path}': {exc}"
            ) from exc
        log.debug('LocalDriver uploaded → %s', path)
        return self.get_url(filename)

    def delete(self, filename: str) -> None:
        path = os.path.join(self.config['PATH'], filename)
        if not os.path.exists(path):
            raise StorageNotFoundError(
                f"LocalDriver: file not found: {path}"
            )
        try:
            os.remove(path)
        except OSError as exc:
            raise StorageDeleteError(
                f"LocalDriver: delete failed for '{path}': {exc}"
            ) from exc
        log.debug('LocalDriver deleted → %s', path)
