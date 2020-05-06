#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import logging
import sys
import os
import getpass
import platform
import subprocess

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


def git_version(default=None):
    """
    返回当前的git版本, 以供sentry的 release 使用
    
    示例用法:
        sentry.setup(..., release=git_revision())
    
    Return the git revision as a string
    
    References:
        https://github.com/numpy/numpy/blob/master/setup.py#L71-L93
    """
    
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH', 'HOME']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out
    
    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', '--short', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except:
        git_revision = default
    
    return git_revision


client = None  # type: raven.Client


def setup(dsn=None, name=None, level=logging.WARNING,
          autoversion=True,
          **kwargs):
    global client
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    
    if not dsn:
        raise ValueError("you must give SENTRY_DSN, or set it in env")

    if kwargs.get('string_max_length') is None:
        kwargs['string_max_length'] = 4096
    if autoversion and kwargs.get('release') is None:
        release = git_version()
        if release:
            kwargs['release'] = release
    if kwargs.get('ignore_exceptions') is None:
        kwargs['ignore_exceptions'] = [KeyboardInterrupt]
    if kwargs.get('auto_log_stacks') is None:
        kwargs['auto_log_stacks'] = True
    
    client = raven.Client(
        dsn,
        name=name,
        processors=raven.conf.defaults.PROCESSORS + (
            AdditionalInfoProcessor.__module__ + "." + AdditionalInfoProcessor.__name__,),
        **kwargs
    )
    handler = raven.handlers.logging.SentryHandler(client)
    handler.setLevel(level)
    raven.conf.setup_logging(handler)
    
    return client
