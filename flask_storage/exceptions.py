"""
flask_storage.exceptions
------------------------
All exceptions raised by flask-storage inherit from ``StorageError``,
so callers can catch broadly or narrowly::

    from flask_storage import StorageError, StorageUploadError

    try:
        url = storage.upload(f, name)
    except StorageUploadError as exc:
        log.error("upload failed: %s", exc)
        abort(500)
    except StorageError:
        abort(500)
"""


class StorageError(Exception):
    """Base for every flask-storage exception."""


class StorageConfigError(StorageError):
    """
    Provider is missing, misconfigured, or an unknown name was requested.
    Raised at instantiation time, never during I/O.
    """


class StorageUploadError(StorageError):
    """Upload to the backend failed."""


class StorageDeleteError(StorageError):
    """Delete from the backend failed for a reason other than not-found."""


class StorageNotFoundError(StorageDeleteError):
    """
    The file targeted for deletion does not exist on the backend.
    Subclasses ``StorageDeleteError`` so broad catches still work.
    """
