#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="scholar-search",
    version="0.0.6",
    license="MIT",
    description="a macro search bar",
    author="Adam Miller",
    author_email="miller@adammiller.io",
    url="https://github.com/adammillerio/sch",
    download_url="https://github.com/adammillerio/sch/archive/v0.0.6.tar.gz",
    keywords=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "anytree",
        "flask",
        "click",
        "pypandoc",
    ],
    extras_require={"pandoc": ["pypandoc-binary"], "dev": ["ruff", "pyre-check"]},
    entry_points="""
    [console_scripts]
    sch=sch.cli:sch
  """,
)
