#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, unicode_literals
import os
import sys
import traceback
import logging
import logging.handlers
import requests
import inspect
import getpass
import platform
from err_hunter.attr import attributes

PY2 = (sys.version_info[0] == 2)


def real_frame_extract(subframe, filepath, lineno):
    """
    :type subframe: inspect.FrameInfo
    :rtype: inspect.FrameInfo
    """
    frames = inspect.getouterframes(subframe)
    for frame in frames:
        if PY2:
            if frame[1] == filepath and frame[2] == lineno:
                return frame[0]  # type: inspect.FrameInfo
        elif frame.filename == filepath and frame.lineno == lineno:
            return frame.frame  # type: inspect.FrameInfo
    
    return None


class MyHTTPHandler(logging.Handler):
    def __init__(self, url, interested=None,
                 method="POST", level=logging.WARNING, callback=None, timeout=10, req_kwargs=None):
        super(MyHTTPHandler, self).__init__(level)
        
        self.url = url
        self.method = method
        self.req_kwargs = req_kwargs or {}
        self.session = requests.Session()
        self.callback = callback
        self.timeout = timeout
        self.interested = interested
    
    def mapLogRecord(self, record):
        data = {}
        data.update(record.__dict__)
        
        data.update({
            "_cwd": os.getcwd(),
            "_username": getpass.getuser(),
            "_hostname": platform.node(),
            "_uname": str(platform.uname()),
            "_py_version": sys.version,
        })
        
        if record.levelno >= logging.ERROR:
            real_frame = real_frame_extract(
                inspect.currentframe(),
                filepath=data["pathname"],
                lineno=data["lineno"]
            )
            
            if real_frame is not None:
                global_vars = attributes(real_frame.f_globals, interested=self.interested, from_dict=True)
                local_vars = attributes(real_frame.f_locals, interested=self.interested, from_dict=True)
                
                data["_global_vars"] = global_vars
                data["_local_vars"] = local_vars
        
        if sys.exc_info() != (None, None, None):
            data["_traceback"] = traceback.format_exc()
        
        return data
    
    def _emit(self, record):
        """:type record: logging.LogRecord"""
        
        kwargs = {"timeout": self.timeout}
        data = self.mapLogRecord(record)  # type: dict
        
        if self.method == "GET":
            kwargs["params"] = data
        else:
            kwargs["data"] = data
        
        kwargs.update(self.req_kwargs)
        resp = self.session.request(
            self.method, self.url, **kwargs
        )
        if self.callback is not None:
            self.callback(record, resp)
    
    def emit(self, record):
        try:
            self._emit(record)
        except:
            self.handleError(record)
