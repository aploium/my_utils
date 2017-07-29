#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
from setuptools import setup, find_packages

import err_hunter

PACKAGE = "err_hunter"
NAME = "err-hunter"
DESCRIPTION = "Enhanced traceback and logging utils"
AUTHOR = "aploium"
AUTHOR_EMAIL = "i@z.codes"
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
        'Development Status :: 3 - Alpha',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)