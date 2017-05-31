#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import logging
import sys
import os
import getpass
import platform
import raven
import raven.conf
import raven.conf.defaults
import raven.processors
import raven.handlers.logging


class AdditionalInfoProcessor(raven.processors.Processor):
    def filter_extra(self, data):
        """:type data: dict"""
        
        data.update({
            "cwd": os.getcwd(),
            "user": getpass.getuser(),
            "uname": platform.uname(),
            "py_version": sys.version,
        })
        
        return data


client = None


def setup(dsn=None, level=logging.WARNING, **kwargs):
    global client
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    
    if not dsn:
        raise ValueError("you must give SENTRY_DSN, or set it in env")
    
    client = raven.Client(
        dsn,
        processors=raven.conf.defaults.PROCESSORS + ("sentry.AdditionalInfoProcessor",),
        **kwargs
    )
    handler = raven.handlers.logging.SentryHandler(client)
    handler.setLevel(level)
    raven.conf.setup_logging(handler)
    
    return client
