#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import
import logging
from err_hunter.mylogger import MyHTTPHandler

__version__ = (2017, 5, 31, 1)
__author__ = "Aploium<i@z.codes>"


def apply_handler(url,
                  level=logging.WARNING,
                  method="POST",
                  interested=None,
                  parent_name=None,
                  callback=None,
                  timeout=10,
                  req_kwargs=None,
                  source_path=None,
                  ):
    handler = MyHTTPHandler(
        url, interested=interested,
        method=method, level=level,
        callback=callback, timeout=timeout,
        req_kwargs=req_kwargs,
        source_path=source_path,
    )
    handler.setFormatter(logging.Formatter())
    logging.getLogger(parent_name).addHandler(handler)
    return handler
