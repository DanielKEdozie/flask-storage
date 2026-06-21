"""
flask_storage.storage
---------------------
:class:`Storage`      — per-request provider facade.
:class:`FlaskStorage` — Flask extension (app-factory pattern).

One ``init_app`` call wires everything — config defaults, the extension
registry entry, optional API routes, and an optional allowed-extensions
guard::

    # extensions.py
    from flask_storage import FlaskStorage
    storage = FlaskStorage()

    # app factory
    storage.init_app(app, api_bp)   # registers upload/delete routes on api_bp

Routes registered when api_bp is supplied
------------------------------------------
    POST   <upload_url_prefix>/upload        Upload a file → { url, filename }
    DELETE <upload_url_prefix>/delete/<name> Delete a stored file → 204
"""
from __future__ import annotations

import importlib
import logging
import uuid
from typing import IO, Any

from werkzeug.utils import secure_filename

from .exceptions import StorageConfigError
from .utils import file_extension
from flask import current_app
from .processors import WatermarkProcessor

log = logging.getLogger(__name__)

# ── Driver registry ────────────────────────────────────────────────────────────

_REGISTRY: dict[str, str] = {
    'local'      : 'flask_storage.drivers.local.LocalDriver',
    's3'         : 'flask_storage.drivers.s3.S3Driver',
    'gcs'        : 'flask_storage.drivers.gcs.GCSDriver',
    'azure'      : 'flask_storage.drivers.azure.AzureDriver',
    'cloudinary' : 'flask_storage.drivers.cloudinary.CloudinaryDriver',
}


def _import_driver(dotted: str) -> type:
    module_path, cls_name = dotted.rsplit('.', 1)
    return getattr(importlib.import_module(module_path), cls_name)


# ── Storage facade ─────────────────────────────────────────────────────────────

class Storage:
    """
    Provider-agnostic storage facade.

    Must be instantiated inside a Flask app or request context.
    Reads ``DEFAULT_STORAGE`` and ``STORAGES`` from ``current_app.config``,
    resolves the driver, and delegates all I/O to it.

    Every upload is renamed to ``<uuid4_hex>.<ext>`` — filenames are
    always unique, safe, and path-traversal-free.

    :param provider: Override ``DEFAULT_STORAGE`` for this call only.

    Usage::

        # default provider
        url = Storage().upload(request.files['photo'], 'photo.jpg')

        # explicit provider
        url = Storage('s3').upload(f, name)

        # delete
        Storage().delete('a1b2c3.jpg')

        # URL without I/O
        url = Storage().get_url('a1b2c3.jpg')
    """

    def __init__(self, provider: str | None = None) -> None:
        from flask import current_app

        self._provider = provider or current_app.config.get('DEFAULT_STORAGE', 'local')

        storages: dict[str, Any] = current_app.config.get('STORAGES', {})
        config = storages.get(self._provider)

        if config is None:
            raise StorageConfigError(
                f"Provider '{self._provider}' not found in app.config['STORAGES']. "
                f"Configured: {list(storages) or '(none)'}."
            )

        dotted = _REGISTRY.get(self._provider)
        if dotted is None:
            raise StorageConfigError(
                f"No driver for '{self._provider}'. "
                f"Built-in: {list(_REGISTRY)}. "
                f"Register custom drivers with FlaskStorage.register_driver()."
            )

        self._driver = _import_driver(dotted)(config)

    @property
    def provider(self) -> str:
        return self._provider

    def upload(self, file_obj: IO[bytes], original_filename: str, watermark: bool = None) -> tuple[str, str]:
        """
        UUID-rename, upload, and return ``(url, stored_filename)``.

        Returns the filename alongside the URL so callers can store it
        for future ``delete()`` calls without parsing the URL.

        :raises StorageUploadError:
        """
        should_watermark = watermark if watermark is not None else current_app.config.get('WATERMARK', False)
        
        final_file = file_obj
        
        # 2. Process Watermark if enabled
        if should_watermark:
            wm_path = current_app.config.get('WATERMARK_PATH')
            if wm_path:
                processor = WatermarkProcessor(
                    path=wm_path,
                    opacity=current_app.config.get('WATERMARK_OPACITY', 0.5),
                    position=current_app.config.get('WATERMARK_POSITION', 'center'),
                    size=current_app.config.get('WATERMARK_SIZE', 15)
                )
                # apply returns a BytesIO stream
                final_file = processor.apply(file_obj)
            else:
                log.warning("Watermark enabled but WATERMARK_PATH not configured.")
        name = _unique_name(original_filename)
        log.info('Storage.upload provider=%s name=%s', self._provider, name)
        url = self._driver.upload(final_file, name)
        return url, name

    def delete(self, filename: str) -> None:
        """
        Delete by stored filename (not URL).

        :raises StorageNotFoundError:
        :raises StorageDeleteError:
        """
        name = secure_filename(filename)
        log.info('Storage.delete provider=%s name=%s', self._provider, name)
        self._driver.delete(name)

    def get_url(self, filename: str) -> str:
        """Return the public URL without making a network call."""
        return self._driver.get_url(filename)


# ── FlaskStorage extension ─────────────────────────────────────────────────────

class FlaskStorage:
    """
    Flask extension that wires :class:`Storage` into an application.

    App-factory pattern::

        # extensions.py
        from flask_storage import FlaskStorage
        storage = FlaskStorage()

        # app factory
        from .extensions import storage
        storage.init_app(app, api_bp)

        # in any view
        url, filename = storage.upload(request.files['photo'], 'photo.jpg')
        storage.delete(filename)
        url = storage.get_url(filename)

    Direct initialisation::

        storage = FlaskStorage(app)

    Optional: skip API route registration by omitting api_bp::

        storage.init_app(app)   # no upload/delete routes registered

    Custom driver::

        FlaskStorage.register_driver('minio', 'myapp.drivers.MinioDriver')
    """

    def __init__(self, app: Any = None, **kwargs) -> None:
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(
        self,
        app,
        api_bp                   = None,
        *,
        upload_url_prefix: str   = '/uploads',
        allowed_extensions: set  = None,
        max_content_length: int  = None,
        route_configs: dict      = None,
    ) -> None:
        """
        Bind FlaskStorage to *app*.

        Parameters
        ----------
        app                Flask application instance.
        api_bp             Blueprint or app to register upload/delete routes on.
                           When omitted no routes are registered.
        upload_url_prefix  URL prefix for upload routes (default ``'/uploads'``).
        allowed_extensions Set of lowercase extensions without dots, e.g.
                           ``{'jpg', 'png', 'pdf'}``.  When supplied every
                           upload is validated against this set.  When omitted
                           all extensions are accepted.
                           Also reads ``ALLOWED_EXTENSIONS`` from app config
                           as a fallback.
        max_content_length Hard cap on upload size in bytes.  Sets
                           ``app.config['MAX_CONTENT_LENGTH']`` when given.
        route_configs      Per-action decorator dict::

                               {
                                   'upload': [login_required],
                                   'delete': [login_required, admin_required],
                               }
        """
        app.config.setdefault('DEFAULT_STORAGE', 'local')
        app.config.setdefault('STORAGES', {})

        if allowed_extensions is not None:
            app.config['ALLOWED_EXTENSIONS'] = {
                e.lower().lstrip('.') for e in allowed_extensions
            }

        if max_content_length is not None:
            app.config['MAX_CONTENT_LENGTH'] = max_content_length

        app.extensions['flask_storage'] = self
        log.debug(
            'FlaskStorage init: default_provider=%s',
            app.config['DEFAULT_STORAGE'],
        )

        if api_bp is not None:
            from .views import StorageViews
            StorageViews(
                api_bp,
                url_prefix    = upload_url_prefix,
                route_configs = route_configs or {},
            )

    # ── Proxy methods ──────────────────────────────────────────────────────────

    def upload(
        self,
        file_obj: IO[bytes],
        original_filename: str,
        provider: str | None = None,
        watermark: bool | None = None,
    ) -> tuple[str, str]:
        """Proxy to :meth:`Storage.upload`. Returns ``(url, filename)``."""
        return Storage(provider).upload(file_obj, original_filename, watermark=watermark)

    def delete(self, filename: str, provider: str | None = None) -> None:
        """Proxy to :meth:`Storage.delete`."""
        Storage(provider).delete(filename)

    def get_url(self, filename: str, provider: str | None = None) -> str:
        """Proxy to :meth:`Storage.get_url`."""
        return Storage(provider).get_url(filename)

    @staticmethod
    def register_driver(name: str, dotted_path: str) -> None:
        """
        Register a custom driver.

        :param name:         Provider name for ``STORAGES`` / ``DEFAULT_STORAGE``.
        :param dotted_path:  Dotted import path to the driver class.

        Example::

            FlaskStorage.register_driver('minio', 'myapp.storage.MinioDriver')
        """
        _REGISTRY[name] = dotted_path
        log.debug('FlaskStorage: registered driver "%s" → %s', name, dotted_path)


# ── Private helpers ────────────────────────────────────────────────────────────

def _unique_name(original_filename: str) -> str:
    ext = file_extension(secure_filename(original_filename))
    return f'{uuid.uuid4().hex}{ext}'
