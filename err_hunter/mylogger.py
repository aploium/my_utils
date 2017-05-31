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
from err_hunter import frame_operations


class MyHTTPHandler(logging.Handler):
    def __init__(self, url, interested=None,
                 method="POST", level=logging.WARNING, callback=None, timeout=10, req_kwargs=None,
                 source_path=None
                 ):
        super(MyHTTPHandler, self).__init__(level)
        
        self.url = url
        self.method = method
        self.req_kwargs = req_kwargs or {}
        self.session = requests.Session()
        self.callback = callback
        self.timeout = timeout
        self.interested = interested
        self.source_path = source_path or os.getcwd()
    
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
            real_frame = frame_operations.real_frame_extract(
                inspect.currentframe(),
                filepath=data["pathname"],
                lineno=data["lineno"]
            )
            
            if real_frame is not None:
                data["_logframe"] = frame_operations.frame_format(real_frame, interested=self.interested)
        
        if sys.exc_info() != (None, None, None) and "_traceback" not in data:
            data["_traceback"] = traceback.format_exc()
            
            _traceback_frames = ""
            
            for frame, lineno in traceback.walk_tb(sys.exc_info()[2]):
                abs_path = frame.f_code.co_filename
                if ".." not in os.path.relpath(abs_path, self.source_path):
                    _traceback_frames += frame_operations.frame_format(
                        frame, interested=self.interested, frame_lineno=lineno
                    ) + "\n"
            
            data["_traceback_frames"] = _traceback_frames
        
        return data
    
    def _emit(self, record):
        """:type record: logging.LogRecord"""
        
        kwargs = {"timeout": self.timeout, "allow_redirects": False}
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
