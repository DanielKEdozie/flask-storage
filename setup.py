from setuptools import setup, find_packages

setup(
    name             = 'flask-storage',
    version          = '1.0.0',
    description      = 'Multi-provider file-storage extension for Flask',
    packages         = find_packages(exclude=['tests*']),
    python_requires  = '>=3.9',
    install_requires = [
        'Flask>=2.0',
        'Werkzeug>=2.0',
        'pillow>=9.0.1',
    ],
    extras_require = {
        's3'         : ['boto3>=1.20'],
        'gcs'        : ['google-cloud-storage>=2.0'],
        'azure'      : ['azure-storage-blob>=12.0'],
        'cloudinary' : ['cloudinary>=1.30'],
        'all'        : [
            'boto3>=1.20',
            'google-cloud-storage>=2.0',
            'azure-storage-blob>=12.0',
            'cloudinary>=1.30',
        ],
    },
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Framework :: Flask',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
