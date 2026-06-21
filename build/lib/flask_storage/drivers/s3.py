"""
flask_storage.drivers.s3
------------------------
Stores files in Amazon S3 or any S3-compatible service
(MinIO, DigitalOcean Spaces, Backblaze B2, Cloudflare R2, …).

Required config keys
--------------------
    ACCESS_KEY   AWS / service access key ID.
    SECRET_KEY   AWS / service secret access key.
    REGION       Region string, e.g. ``us-east-1``.
    BUCKET_NAME  Target bucket name.

Optional config keys
--------------------
    ENDPOINT_URL   Override endpoint for S3-compatible services.
    ACL            Canned ACL for every upload (default: ``public-read``).
    URL            CDN base URL override; when absent the canonical S3 URL
                   is constructed from bucket + region.
"""
from __future__ import annotations

import logging
from typing import IO, Any

from .base import StorageDriver
from ..exceptions import StorageDeleteError, StorageNotFoundError, StorageUploadError
from ..utils import require_keys

log = logging.getLogger(__name__)

_REQUIRED = ('ACCESS_KEY', 'SECRET_KEY', 'REGION', 'BUCKET_NAME')


class S3Driver(StorageDriver):

    def __init__(self, config: dict[str, Any]) -> None:
        require_keys(config, _REQUIRED, 's3')
        super().__init__(config)

        import boto3  # lazy — only loaded when this driver is used

        kw: dict[str, Any] = dict(
            aws_access_key_id     = config['ACCESS_KEY'],
            aws_secret_access_key = config['SECRET_KEY'],
            region_name           = config['REGION'],
        )
        if ep := config.get('ENDPOINT_URL'):
            kw['endpoint_url'] = ep

        self._client = boto3.client('s3', **kw)
        self._bucket = config['BUCKET_NAME']
        self._acl    = config.get('ACL', 'public-read')

    def upload(self, file_obj: IO[bytes], filename: str) -> str:
        try:
            self._client.upload_fileobj(
                file_obj,
                self._bucket,
                filename,
                ExtraArgs={'ACL': self._acl},
            )
        except Exception as exc:
            raise StorageUploadError(
                f"S3Driver: upload failed for '{filename}': {exc}"
            ) from exc
        log.debug('S3Driver uploaded → s3://%s/%s', self._bucket, filename)
        return self.get_url(filename)

    def delete(self, filename: str) -> None:
        # head_object raises ClientError(404) when the key is absent.
        try:
            self._client.head_object(Bucket=self._bucket, Key=filename)
        except Exception as exc:
            code = getattr(exc, 'response', {}).get('Error', {}).get('Code', '')
            if code == '404':
                raise StorageNotFoundError(
                    f"S3Driver: key not found: s3://{self._bucket}/{filename}"
                ) from exc
            raise StorageDeleteError(
                f"S3Driver: existence check failed for '{filename}': {exc}"
            ) from exc

        try:
            self._client.delete_object(Bucket=self._bucket, Key=filename)
        except Exception as exc:
            raise StorageDeleteError(
                f"S3Driver: delete failed for '{filename}': {exc}"
            ) from exc
        log.debug('S3Driver deleted → s3://%s/%s', self._bucket, filename)

    def get_url(self, filename: str) -> str:
        if cdn := self.config.get('URL'):
            return f"{cdn.rstrip('/')}/{filename}"
        return (
            f"https://{self._bucket}"
            f".s3.{self.config['REGION']}.amazonaws.com/{filename}"
        )
