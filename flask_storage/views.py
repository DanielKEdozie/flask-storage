"""
flask_storage.views
-------------------
Plug-and-play file upload / delete route factory.

Works identically to ``ApiMixin`` — instantiate once and the routes
are live on any Blueprint or Flask app::

    from flask_storage.views import StorageViews

    StorageViews(api_bp, url_prefix='/uploads')

Routes registered
-----------------
    POST   <prefix>/upload           Upload a file.
                                     Body: multipart/form-data, field ``file``.
                                     Returns: ``{ url, filename }``

    DELETE <prefix>/delete/<filename> Delete a stored file by its
                                      stored filename (not the URL).
                                      Returns: 204

Both routes are wired automatically when you pass ``api_bp`` to
:meth:`~flask_storage.FlaskStorage.init_app`.

Customisation
-------------
Per-route decorators::

    StorageViews(api_bp, route_configs={
        'upload': [login_required],
        'delete': [login_required, admin_required],
    })

Custom allowed extensions (overrides app config)::

    StorageViews(api_bp, allowed_extensions={'jpg', 'png', 'webp'})

Custom max upload size::

    StorageViews(api_bp, max_content_length=5 * 1024 * 1024)   # 5 MB
"""
from __future__ import annotations

import logging

from flask import current_app, jsonify, request
from flask.views import MethodView
from werkzeug.exceptions import BadRequest, UnsupportedMediaType
from werkzeug.utils import secure_filename

from .exceptions import StorageError, StorageNotFoundError
from .utils import file_extension

log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_storage():
    """Return the FlaskStorage extension or raise if not initialised."""
    ext = current_app.extensions.get('flask_storage')
    if ext is None:
        raise RuntimeError(
            'FlaskStorage is not initialised on this app. '
            'Call storage.init_app(app) in your app factory.'
        )
    return ext


def _allowed(filename: str) -> bool:
    """
    Return True when *filename* is permitted by ``ALLOWED_EXTENSIONS``.

    If ``ALLOWED_EXTENSIONS`` is absent from app config every file is allowed.
    """
    allowed = current_app.config.get('ALLOWED_EXTENSIONS')
    if not allowed:
        return True
    ext = file_extension(secure_filename(filename)).lstrip('.')
    return ext in allowed


def _apply_decorators(view_func, decorators: list):
    for dec in reversed(decorators):
        if not callable(dec):
            raise TypeError(f'Decorator must be callable, got {type(dec)!r}.')
        view_func = dec(view_func)
    return view_func


# ── View classes ───────────────────────────────────────────────────────────────

class UploadView(MethodView):
    """POST <prefix>/upload — accept a file, store it, return URL + filename."""

    def post(self):
        """
        Upload a file.

        Expects ``multipart/form-data`` with a ``file`` field.

        Returns 201::

            { "url": "https://...", "filename": "a1b2c3d4.jpg" }

        Errors:
            400  No file in request / empty filename
            415  Extension not in ALLOWED_EXTENSIONS
            500  Storage backend failure
        """
        if 'file' not in request.files:
            raise BadRequest('No file field in the request. '
                             'Send multipart/form-data with a "file" field.')

        file = request.files['file']

        if not file.filename:
            raise BadRequest('File field is present but has no filename.')

        if not _allowed(file.filename):
            allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
            raise UnsupportedMediaType(
                f"File type not allowed. "
                f"Permitted extensions: {', '.join(sorted(allowed)) or 'all'}."
            )

        # Get watermark flag from request (form data or JSON).
        # Use explicit None check to avoid AttributeError when request.json is None.
        watermark_raw = request.form.get('watermark')
        if watermark_raw is None and request.is_json and request.json:
            watermark_raw = request.json.get('watermark')

        watermark = None
        if watermark_raw is not None:
            watermark = str(watermark_raw).lower() in ('true', '1', 'yes')

        try:
            url, filename = _get_storage().upload(file, file.filename, watermark=watermark)
        except StorageError as exc:
            log.error('UploadView: storage error: %s', exc)
            # Re-raise as a 500 — the error handler will format it.
            raise

        log.info('UploadView: uploaded filename=%s url=%s', filename, url)
        return jsonify({'url': url, 'filename': filename}), 201


class DeleteView(MethodView):
    """DELETE <prefix>/delete/<filename> — remove a stored file."""

    def delete(self, filename: str):
        """
        Delete a file by its stored filename.

        :param filename: The UUID-based filename returned by the upload
                         endpoint (not the full URL).

        Returns 204 on success.

        Errors:
            400  Filename is unsafe / empty
            404  File not found on the backend
            500  Storage backend failure
        """
        safe = secure_filename(filename)
        if not safe:
            raise BadRequest('Invalid filename.')

        try:
            _get_storage().delete(safe)
        except StorageNotFoundError as exc:
            from werkzeug.exceptions import NotFound
            raise NotFound(str(exc))
        except StorageError as exc:
            log.error('DeleteView: storage error: %s', exc)
            raise

        log.info('DeleteView: deleted filename=%s', safe)
        return '', 204


# ── StorageViews factory ───────────────────────────────────────────────────────

class StorageViews:
    """
    Register file upload and delete routes on a Blueprint or app.

    Mirrors ``ApiMixin`` usage — instantiate once and routes are live::

        from flask_storage.views import StorageViews

        StorageViews(api_bp, url_prefix='/uploads')

    :param app_or_bp:          Blueprint or Flask app.
    :param url_prefix:         Route prefix (default ``'/uploads'``).
    :param route_configs:      Per-action decorator dict.
                               Actions: ``'upload'``, ``'delete'``.
    :param allowed_extensions: Override ``ALLOWED_EXTENSIONS`` for these
                               routes only.  Pass a set of lowercase
                               extensions without dots.
    :param max_content_length: Per-route upload size cap in bytes.
                               Sets ``app.config['MAX_CONTENT_LENGTH']``
                               when provided at init time.
    """

    def __init__(
        self,
        app_or_bp,
        url_prefix:          str  = '/uploads',
        route_configs:       dict = None,
        allowed_extensions:  set  = None,
        max_content_length:  int  = None,
    ) -> None:
        self._bp           = app_or_bp
        self._prefix       = url_prefix.rstrip('/')
        self._route_cfgs   = route_configs or {}

        # Store extension constraints so the views can read them.
        if allowed_extensions is not None:
            self._allowed_extensions = {
                e.lower().lstrip('.') for e in allowed_extensions
            }
        else:
            self._allowed_extensions = None

        self._max_content_length = max_content_length

        self._register_routes()

    def _decorators(self, action: str) -> list:
        raw = self._route_cfgs.get(action, [])
        return [raw] if callable(raw) and not isinstance(raw, list) else list(raw)

    def _register_routes(self) -> None:
        p = self._prefix

        upload_view = UploadView.as_view('storage_upload')
        upload_view = _apply_decorators(upload_view, self._decorators('upload'))
        self._bp.add_url_rule(
            f'{p}/upload',
            endpoint  = 'storage_upload',
            view_func = upload_view,
            methods   = ['POST'],
        )

        delete_view = DeleteView.as_view('storage_delete')
        delete_view = _apply_decorators(delete_view, self._decorators('delete'))
        self._bp.add_url_rule(
            f'{p}/delete/<filename>',
            endpoint  = 'storage_delete',
            view_func = delete_view,
            methods   = ['DELETE'],
        )

        log.debug('StorageViews registered: prefix=%s', p)
