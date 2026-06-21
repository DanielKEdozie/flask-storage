# flask-storage — Usage Guide

## Installation

```bash
pip install flask-storage
# or drop the flask_storage/ folder into your project root
```

Provider-specific extras:

```bash
pip install flask-storage[s3]          # Amazon S3 / S3-compatible
pip install flask-storage[gcs]         # Google Cloud Storage
pip install flask-storage[azure]       # Azure Blob Storage
pip install flask-storage[cloudinary]  # Cloudinary
pip install flask-storage[all]         # all providers
```

---

## Quick start

### 1. Extension

```python
# app/extensions.py
from flask_storage import FlaskStorage
storage = FlaskStorage()
```

### 2. App factory

```python
# app/__init__.py
from flask import Flask, Blueprint
from .extensions import storage

def create_app(config='development'):
    app = Flask(__name__)
    app.config.from_object(f'config.{config.title()}Config')

    api_bp = Blueprint('api', __name__)

    # One call — config defaults, extension, API routes all wired.
    storage.init_app(
        app,
        api_bp,
        upload_url_prefix  = '/uploads',
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf'},
        max_content_length = 10 * 1024 * 1024,   # 10 MB
    )

    app.register_blueprint(api_bp, url_prefix='/api')
    return app
```

### 3. Config

```python
# config.py
DEFAULT_STORAGE = 'local'

# Watermark Global Settings
WATERMARK = True               # Global toggle
WATERMARK_PATH = 'logo.png'    # Path to PNG
WATERMARK_OPACITY = 0.3        # 0.0 to 1.0
WATERMARK_POSITION = 'center'  # center, bottom-right, tiled

STORAGES = {
    'local': {
        'PATH': '/var/uploads/',
        'URL' : 'http://localhost:5000/uploads/',
    },
}
```

---

## API routes

Both routes are registered automatically when `api_bp` is passed to `init_app`.

### `POST /api/uploads/upload`

Upload a file via `multipart/form-data`.

**Request** — form field name must be `file`:

```
POST /api/uploads/upload
Content-Type: multipart/form-data

file=<binary>
```

**Response 201**

```json
{ "url": "http://localhost:5000/uploads/a1b2c3d4.jpg", "filename": "a1b2c3d4.jpg" }
```

Store `filename` in your database — you will need it to call the delete endpoint.

| Status | When |
|--------|------|
| `201` | Uploaded successfully |
| `400` | No file field / empty filename |
| `415` | Extension not in `ALLOWED_EXTENSIONS` |
| `500` | Storage backend error |

---

### `DELETE /api/uploads/delete/<filename>`

Delete a stored file by its UUID-based filename.

```
DELETE /api/uploads/delete/a1b2c3d4.jpg
```

**Response** `204 No Content`

| Status | When |
|--------|------|
| `204` | Deleted successfully |
| `400` | Filename is unsafe / empty |
| `404` | File not found on the backend |
| `500` | Storage backend error |

---

## Using storage in your own views

```python
from flask import request
from app.extensions import storage

# Upload
url, filename = storage.upload(request.files['photo'], 'photo.jpg')
# url      → 'http://localhost:5000/uploads/a1b2c3d4.jpg'
# filename → 'a1b2c3d4.jpg'  ← store this in your DB

# Delete
storage.delete(filename)

# Get URL for an already-stored file
url = storage.get_url(filename)

# Explicit provider override for one operation
url, filename = storage.upload(f, name, provider='s3')
```

> **Breaking change from v1:** `storage.upload()` now returns
> `(url, filename)` instead of just `url`.  This makes it easy to
> store the filename without parsing the URL.

---

## Provider configs

### Local

```python
STORAGES = {
    'local': {
        'PATH': '/var/uploads/',          # absolute path, auto-created
        'URL' : 'http://localhost:5000/uploads/',
    },
}
```

### Amazon S3

```bash
pip install flask-storage[s3]
```

```python
STORAGES = {
    's3': {
        'ACCESS_KEY'  : 'AKIA...',
        'SECRET_KEY'  : '...',
        'REGION'      : 'us-east-1',
        'BUCKET_NAME' : 'my-bucket',
        # optional
        'ENDPOINT_URL': 'https://...',    # S3-compatible (MinIO, R2, Spaces…)
        'ACL'         : 'public-read',    # default
        'URL'         : 'https://cdn.example.com/',  # CDN override
    },
}
```

### Google Cloud Storage

```bash
pip install flask-storage[gcs]
```

```python
STORAGES = {
    'gcs': {
        'PROJECT_ID'  : 'my-project',
        'BUCKET_NAME' : 'my-bucket',
        'URL'         : 'https://cdn.example.com/',  # optional CDN
    },
}
```

### Azure Blob Storage

```bash
pip install flask-storage[azure]
```

```python
STORAGES = {
    'azure': {
        'ACCOUNT_NAME'   : 'myaccount',
        'ACCOUNT_KEY'    : '...',
        'CONTAINER_NAME' : 'uploads',
        'URL'            : 'https://cdn.example.com/',  # optional CDN
    },
}
```

### Cloudinary

```bash
pip install flask-storage[cloudinary]
```

```python
STORAGES = {
    'cloudinary': {
        'CLOUD_NAME': 'my-cloud',
        'API_KEY'   : '...',
        'API_SECRET': '...',
    },
}
```

---

## Protecting routes

```python
from flask_login import login_required
from flask_storage.views import StorageViews

StorageViews(
    api_bp,
    url_prefix    = '/uploads',
    route_configs = {
        'upload': [login_required],
        'delete': [login_required],
    },
)
```

Or via `init_app`:

```python
storage.init_app(
    app,
    api_bp,
    route_configs = {
        'upload': [login_required],
        'delete': [login_required],
    },
)
```

---

## Allowed extensions

Set globally via config:

```python
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'docx'}
```

Or at init time (takes precedence over config):

```python
storage.init_app(
    app,
    api_bp,
    allowed_extensions = {'jpg', 'jpeg', 'png'},
)
```

When a disallowed extension is uploaded the endpoint returns:

```json
HTTP 415 Unsupported Media Type
{ "error": "File type not allowed. Permitted extensions: jpg, jpeg, png." }
```

---

## Upload size limit

```python
storage.init_app(
    app,
    api_bp,
    max_content_length = 5 * 1024 * 1024,   # 5 MB
)
```

Flask enforces this with a `413 Request Entity Too Large` response.

---

## Switching providers

Change only config — no code changes needed:

```python
DEFAULT_STORAGE = 's3'
```

---

## Custom drivers

```python
from flask_storage.drivers.base import StorageDriver
from flask_storage import FlaskStorage
from flask_storage.exceptions import StorageUploadError, StorageDeleteError

class MinioDriver(StorageDriver):
    def __init__(self, config):
        super().__init__(config)
        # initialise Minio client...

    def upload(self, file_obj, filename) -> str:
        # upload and return URL...

    def delete(self, filename) -> None:
        # delete...

FlaskStorage.register_driver('minio', 'myapp.storage.MinioDriver')
```

```python
STORAGES = {
    'minio': {
        'ENDPOINT': 'http://localhost:9000',
        'ACCESS_KEY': '...',
        'SECRET_KEY': '...',
        'BUCKET_NAME': 'uploads',
    },
}
DEFAULT_STORAGE = 'minio'
```

---

## Exception reference

| Exception | When |
|-----------|------|
| `StorageError` | Base — catches all below |
| `StorageConfigError` | Provider missing, misconfigured, or unknown name |
| `StorageUploadError` | Upload to backend failed |
| `StorageDeleteError` | Delete from backend failed |
| `StorageNotFoundError` | File not found during delete (subclass of `StorageDeleteError`) |

```python
from flask_storage import StorageUploadError, StorageNotFoundError

try:
    url, filename = storage.upload(f, name)
except StorageUploadError as exc:
    abort(500, str(exc))
```

---

## Standalone `StorageViews` (without init_app auto-registration)

```python
from flask_storage.views import StorageViews

StorageViews(
    api_bp,
    url_prefix          = '/uploads',
    allowed_extensions  = {'jpg', 'png'},
    max_content_length  = 10 * 1024 * 1024,
    route_configs       = {
        'upload': [login_required],
        'delete': [login_required],
    },
)
```
