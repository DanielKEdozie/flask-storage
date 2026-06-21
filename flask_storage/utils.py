"""
flask_storage.utils
-------------------
Internal helpers.  Not part of the public API.
"""
from __future__ import annotations

import os

from .exceptions import StorageConfigError


def require_keys(config: dict, keys: tuple[str, ...], provider: str) -> None:
    """
    Raise ``StorageConfigError`` if any key in *keys* is absent from *config*.

    :param config:   Provider config dict from ``app.config['STORAGES'][name]``.
    :param keys:     Required key names.
    :param provider: Provider name for the error message.
    """
    missing = [k for k in keys if k not in config or not config[k]]
    if missing:
        raise StorageConfigError(
            f"Storage provider '{provider}' is missing required config "
            f"key(s): {', '.join(missing)}."
        )


def file_extension(filename: str) -> str:
    """
    Return the lowercased extension including the leading dot, or ``''``.

    Dotfiles and extension-less names both return ``''``.

    >>> file_extension('photo.JPG')       # '.jpg'
    >>> file_extension('archive.tar.gz')  # '.gz'
    >>> file_extension('.env')            # ''
    >>> file_extension('README')          # ''
    """
    base = os.path.basename(filename)
    if '.' not in base or base.startswith('.'):
        return ''
    return '.' + base.rsplit('.', 1)[-1].lower()
