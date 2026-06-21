"""
flask_storage.drivers.azure
---------------------------
Stores files in Azure Blob Storage.

Required config keys
--------------------
    ACCOUNT_NAME    Storage account name.
    ACCOUNT_KEY     Storage account access key.
    CONTAINER_NAME  Target container name.

Optional config keys
--------------------
    URL   CDN base URL override.  When absent the canonical Azure Blob URL
          is constructed from account name + container name.
"""
from __future__ import annotations

import logging
from typing import IO, Any

from .base import StorageDriver
from ..exceptions import StorageDeleteError, StorageNotFoundError, StorageUploadError
from ..utils import require_keys

log = logging.getLogger(__name__)

_REQUIRED = ('ACCOUNT_NAME', 'ACCOUNT_KEY', 'CONTAINER_NAME')


class AzureDriver(StorageDriver):

    def __init__(self, config: dict[str, Any]) -> None:
        require_keys(config, _REQUIRED, 'azure')
        super().__init__(config)

        from azure.storage.blob import BlobServiceClient  # lazy import

        conn = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={config['ACCOUNT_NAME']};"
            f"AccountKey={config['ACCOUNT_KEY']};"
            f"EndpointSuffix=core.windows.net"
        )
        service              = BlobServiceClient.from_connection_string(conn)
        self._container      = service.get_container_client(config['CONTAINER_NAME'])
        self._container_name = config['CONTAINER_NAME']
        self._account_name   = config['ACCOUNT_NAME']

    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        try:
            # .read() once: Werkzeug FileStorage may not be seekable after
            # the framework has already consumed request headers.
            data = file_obj.read() if hasattr(file_obj, 'read') else file_obj
            self._container.upload_blob(name=filename, data=data, overwrite=True)
        except Exception as exc:
            raise StorageUploadError(
                f"AzureDriver: upload failed for '{filename}': {exc}"
            ) from exc
        log.debug('AzureDriver uploaded → %s/%s', self._container_name, filename)
        return self.get_url(filename)

    def delete(self, filename: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError  # lazy import

        try:
            self._container.get_blob_client(filename).delete_blob()
        except ResourceNotFoundError as exc:
            raise StorageNotFoundError(
                f"AzureDriver: blob not found: {self._container_name}/{filename}"
            ) from exc
        except Exception as exc:
            raise StorageDeleteError(
                f"AzureDriver: delete failed for '{filename}': {exc}"
            ) from exc
        log.debug('AzureDriver deleted → %s/%s', self._container_name, filename)

    def get_url(self, filename: str) -> str:
        if cdn := self.config.get('URL'):
            return f"{cdn.rstrip('/')}/{filename}"
        return (
            f"https://{self._account_name}.blob.core.windows.net"
            f"/{self._container_name}/{filename}"
        )
