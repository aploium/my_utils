#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import os
import sys
import platform
import functools


def import_helper(relpath, name):
    dirname = os.path.dirname(os.path.abspath(__file__))
    abspath = os.path.join(dirname, relpath)
    sys.path.insert(0, abspath)
    
    if sys.version_info[0] == 2:
        import imp
        module_ = imp.load_module(name, *imp.find_module(name))
    else:
        import importlib
        module_ = importlib.import_module(name)
    sys.path.remove(abspath)
    return module_


_mode = None
VERBOSE_NAME = None
NAME = "leveldb"

if platform.system() == "Windows":
    if sys.version_info[:2] == (3, 6):
        try:
            leveldb = import_helper("leveldb_win_py36", "leveldb")
        except Exception as e:
            raise ImportError(str(e))
        VERBOSE_NAME = "pyleveldb_win_py36"
    
    elif sys.version_info[:2] == (2, 7):
        try:
            leveldb = import_helper("leveldb_win_py27", "leveldb")
        except Exception as e:
            raise ImportError(str(e))
        VERBOSE_NAME = "pyleveldb_win_py27"
    else:
        raise ImportError("unsupported version")
    _mode = "pyleveldb"

else:
    try:
        import plyvel as leveldb
    except ImportError:
        import leveldb
        
        _mode = "pyleveldb"
        VERBOSE_NAME = "pyleveldb_unix"
    else:
        _mode = "plyvel"
        VERBOSE_NAME = "plyvel_leveldb_unix"

# open
if _mode == "plyvel":
    def open(dbpath, block_cache_size=8 * (2 << 20)):
        return leveldb.DB(dbpath, lru_cache_size=block_cache_size, create_if_missing=True)
    get = leveldb.DB.get
    put = leveldb.DB.put
    delete = leveldb.DB.delete
    close = leveldb.DB.close
    keys = functools.partial(leveldb.DB.iterator, include_value=False)
    values = functools.partial(leveldb.DB.iterator, include_key=False)
    items = leveldb.DB.iterator

elif _mode == "pyleveldb":
    open = leveldb.LevelDB
    get = leveldb.LevelDB.Get
    put = leveldb.LevelDB.Put
    delete = leveldb.LevelDB.Delete
    close = lambda x: None
    keys = functools.partial(leveldb.LevelDB.RangeIter, include_value=False)
    items = leveldb.LevelDB.RangeIter
    
    
    def values(self, *args, **kwargs):
        for x in items(self, *args, **kwargs):
            yield x[1]


else:
    raise ImportError("bad mode: {}".format(_mode))
