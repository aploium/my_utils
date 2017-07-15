#!/usr/bin/env python3
# coding=utf-8
"""直接从文件导入成module"""

import importlib.util
import sys
import os


def import_file(path, name=None, make_global=False):
    name = name or os.path.splitext(os.path.basename(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module_ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_)
    
    if make_global:
        sys.modules[name] = module_
    
    return module_
