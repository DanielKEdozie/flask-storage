"""
flask_storage
-------------
Multi-provider file-storage extension for Flask.

Supported built-in providers
-----------------------------
    local · s3 · gcs · azure · cloudinary

Everything — config defaults, extension registration, and API routes —
is wired by a single ``init_app`` call.

Quick start
-----------
::

    # extensions.py
    from flask_storage import FlaskStorage
    storage = FlaskStorage()

    # app/__init__.py
    from .extensions import storage

    def create_app(config='development'):
        app = Flask(__name__)
        app.config.from_object(...)

        api_bp = Blueprint('api', __name__)

        # One call — config defaults set, routes registered on api_bp.
        storage.init_app(
            app,
            api_bp,
            upload_url_prefix  = '/uploads',
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf'},
            max_content_length = 10 * 1024 * 1024,   # 10 MB
        )

        app.register_blueprint(api_bp, url_prefix='/api')
        return app

Routes registered on api_bp
----------------------------
    POST   /api/uploads/upload           { url, filename }
    DELETE /api/uploads/delete/<filename>  204

Using storage in views
----------------------
::

    from .extensions import storage

    # upload
    url, filename = storage.upload(request.files['photo'], 'photo.jpg')

    # delete by stored filename (not the URL)
    storage.delete(filename)

    # get URL for an already-stored file
    url = storage.get_url(filename)

    # explicit provider override
    url, filename = storage.upload(f, name, provider='s3')

Required config (local provider)
----------------------------------
::

    DEFAULT_STORAGE = 'local'
    STORAGES = {
        'local': {
            'PATH': '/var/uploads/',
            'URL' : 'http://localhost:5000/uploads/',
        },
    }

All provider configs
--------------------
::

    STORAGES = {
        'local': {
            'PATH': '/var/uploads/',
            'URL' : 'http://localhost:5000/uploads/',
        },
        's3': {
            'ACCESS_KEY'  : '...',
            'SECRET_KEY'  : '...',
            'REGION'      : 'us-east-1',
            'BUCKET_NAME' : 'my-bucket',
            # optional
            # 'ENDPOINT_URL': '...',   # S3-compatible services
            # 'ACL'         : 'public-read',
            # 'URL'         : 'https://cdn.example.com/',
        },
        'gcs': {
            'PROJECT_ID'  : 'my-project',
            'BUCKET_NAME' : 'my-bucket',
            # optional: 'URL': 'https://cdn.example.com/'
        },
        'azure': {
            'ACCOUNT_NAME'   : 'myaccount',
            'ACCOUNT_KEY'    : '...',
            'CONTAINER_NAME' : 'uploads',
            # optional: 'URL': 'https://cdn.example.com/'
        },
        'cloudinary': {
            'CLOUD_NAME': '...',
            'API_KEY'   : '...',
            'API_SECRET': '...',
        },
    }
"""

from .storage import Storage, FlaskStorage
from .views   import StorageViews
from .exceptions import (
    StorageError,
    StorageConfigError,
    StorageUploadError,
    StorageDeleteError,
    StorageNotFoundError,
)

__version__ = '1.0.0'

__all__ = [
    # Core
    'Storage',
    'FlaskStorage',
    # Views factory
    'StorageViews',
    # Exceptions
    'StorageError',
    'StorageConfigError',
    'StorageUploadError',
    'StorageDeleteError',
    'StorageNotFoundError',
]
