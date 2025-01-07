# setup.py

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="kaltura_uploader",
    version="0.1.0",
    author="Zohar Babin",
    author_email="zohar.babin@kaltura.com",
    description="A robust Python tool for uploading files to Kaltura with chunked and adaptive upload support, automatic MIME type detection, and seamless entry creation for media, document, and data types.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zoharbabin/kaltura_uploader/",
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        "python-dotenv",
        "python-magic",
        "colorlog",
        "requests",
        "requests-toolbelt",
        "KalturaApiClient",
    ],
    entry_points={
        "console_scripts": [
            # This line creates the CLI command `kaltura_uploader` 
            # which executes the function `main` in `kaltura_uploader/cli.py`
            "kaltura_uploader = kaltura_uploader.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License", 
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
