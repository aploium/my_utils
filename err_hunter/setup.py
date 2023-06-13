#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
from setuptools import setup, find_packages

import err_hunter

PACKAGE = "err_hunter"
NAME = "err-hunter"
DESCRIPTION = "Enhanced traceback and logging utils"
AUTHOR = "ap"
AUTHOR_EMAIL = "meow@meow.cat"
URL = "https://github.com/aploium/my_utils/tree/master/err_hunter"

setup(
    name=NAME,
    version=err_hunter.VERSION_STR,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    packages=find_packages(),
    package_dir={
        "err_hunter": "err_hunter",
    },
    package_data={
        "telescope": ["*.json", "*.txt", "*.csv"]
    },
    include_package_data=True,
    platforms="any",
    zip_safe=False,
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ]
)
