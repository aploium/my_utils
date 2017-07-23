#!/usr/bin/env python3
# coding=utf-8
import os
import sys
import traceback

from . import frame_operations


def format_exc(interested=None, source_path=None, with_normal=True):
    if sys.exc_info() == (None, None, None):
        return "NoTraceback"
    
    source_path = source_path or os.getcwd()
    
    _traceback = ""
    
    for frame, lineno in traceback.walk_tb(sys.exc_info()[2]):
        abs_path = frame.f_code.co_filename
        if ".." not in os.path.relpath(abs_path, source_path):
            _traceback += frame_operations.frame_format(
                frame, interested=interested, frame_lineno=lineno
            ) + "\n"
    
    if with_normal:
        _traceback = "{}\n{}".format(traceback.format_exc(), _traceback)
    
    return _traceback


def print_exc(interested=None, source_path=None, with_normal=True):
    print(format_exc(interested=interested, source_path=source_path, with_normal=with_normal))
