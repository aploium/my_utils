#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import

import logging

from .traceback2 import format_exc, print_exc
from .mylogger import MyHTTPHandler
from .third_party import logzero

__version__ = (2017, 7, 23, 1)
__author__ = "Aploium<i@z.codes>"

FORMAT = "[%(levelname)1.1s %(asctime)s %(module)s.%(funcName)s#%(lineno)d] %(message)s"


def basicConfig(level=logging.INFO, color=False):
    logging._acquireLock()
    try:
        if len(logging.root.handlers) != 0:
            return
        handler = logging.StreamHandler()
        formatter = logzero.LogFormatter(color=color)
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        if level is not None:
            logging.root.setLevel(level)
    finally:
        logging._releaseLock()


def colorConfig(level=logging.INFO):
    basicConfig(level=level, color=True)


def getLogger(name=None, logfile=None, level=logging.INFO, formatter=None, maxBytes=0, backupCount=0, fileLoglevel=None):
    return logzero.setup_logger(
        name=name, logfile=logfile, level=level, formatter=None,
        maxBytes=0, backupCount=0, fileLoglevel=None,
    )

def apply_handler(url,
                  level=logging.WARNING,
                  method="POST",
                  interested=None,
                  parent_name=None,
                  callback=None,
                  timeout=10,
                  req_kwargs=None,
                  source_path=None,
                  lazy=False,
                  ):
    if lazy:
        logging.basicConfig(
            format=FORMAT,
            level=logging.INFO,
        )
    
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
