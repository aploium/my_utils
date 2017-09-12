#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import logging
from .third_party import logzero
import inspect


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


def _get_outframe_main(frame):
    outframe = frame.f_back
    return outframe.f_globals["__name__"]


def getLogzeroLogger(name=None, logfile=None, level=logging.NOTSET,
                     formatter=None, maxBytes=0, backupCount=0, fileLoglevel=None):
    name = name or _get_outframe_main(inspect.currentframe())
    
    return logzero.setup_logger(
        name=name, logfile=logfile, level=level, formatter=formatter,
        maxBytes=maxBytes, backupCount=backupCount, fileLoglevel=fileLoglevel,
    )


def getLogger(name=None):
    name = name or _get_outframe_main(inspect.currentframe())
    
    return logging.getLogger(name)
