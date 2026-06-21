"""
flask_storage.drivers.base
--------------------------
Abstract base all storage drivers must implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import IO, Any

from ..exceptions import StorageConfigError


class StorageDriver(ABC):
    """
    Storage driver contract.

    Every driver receives filenames that are already UUID-renamed and
    sanitised by the :class:`~flask_storage.Storage` facade.
    Drivers must never rename files themselves.

    :param config: Provider-specific config dict from
        ``app.config['STORAGES'][provider_name]``.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    # ── Required ──────────────────────────────────────────────────────────────

    @abstractmethod
    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        """
        Write *file_obj* to the backend under *filename*.

        :param file_obj: Readable binary stream.  May be a Werkzeug
            ``FileStorage`` (supports ``.save()``) or a plain ``IO[bytes]``.
        :param filename: Pre-sanitised UUID-based name; do not alter it.
        :returns: Public URL of the stored file.
        :raises StorageUploadError:
        """

    @abstractmethod
    def delete(self, filename: str) -> None:
        """
        Remove *filename* from the backend.

        :raises StorageNotFoundError: file does not exist.
        :raises StorageDeleteError:   any other failure.
        """

    # ── Optional override ─────────────────────────────────────────────────────

    def get_url(self, filename: str) -> str:
        """
        Return the public URL for an already-stored *filename*.

        Default: concatenates ``config['URL']`` + ``filename``.
        Override when the URL scheme differs (e.g. S3 canonical URL).

        :raises StorageConfigError: when ``URL`` is absent from config.
        """
        base = self.config.get('URL', '').rstrip('/')
        if not base:
            raise StorageConfigError(
                f"{self.__class__.__name__} requires a 'URL' key in its "
                f"config to construct public URLs."
            )
        return f"{base}/{filename}"
