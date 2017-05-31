#!/usr/bin/env python3
# coding=utf-8
import logging
import raven
import raven.conf
import raven.conf.defaults
import raven.handlers.logging
import sys
import os
import getpass
import platform
import raven.processors


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


def setup(dsn=None):
    global client

    dsn = dsn or os.getenv("SENTRY_DSN")

    client = raven.Client(
        dsn,
        processors=raven.conf.defaults.PROCESSORS + ("sentry.AdditionalInfoProcessor",)
    )
    handler = raven.handlers.logging.SentryHandler(client)
    handler.setLevel(logging.ERROR)
    raven.conf.setup_logging(handler)

    return client
