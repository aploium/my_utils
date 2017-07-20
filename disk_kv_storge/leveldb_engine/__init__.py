#!/usr/bin/env python3
# coding=utf-8
import os
import sys
import platform
import functools

# -------------------- begin import_file -------------
import importlib.util
import sys
import os


def import_file(path, name=None, make_global=False):
    name = name or os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    module_ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_)
    
    if make_global:
        sys.modules[name] = module_
    
    return module_


# -------------------- end import_file -------------

_mode = None
VERBOSE_NAME = None
NAME = "leveldb"

if platform.system() == "Windows":
    _dirname = os.path.dirname(os.path.abspath(__file__))
    if sys.version_info[:2] == (3, 6):
        try:
            leveldb = import_file(os.path.join(_dirname, "leveldb_win_py36.pyd"), "leveldb")
        except Exception as e:
            raise ImportError(str(e))
        VERBOSE_NAME = "pyleveldb_win_py36"
    
    elif sys.version_info[:2] == (2, 7):
        try:
            leveldb = import_file(os.path.join(_dirname, "leveldb_win_py27.pyd"), "leveldb")
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
    open = functools.partial(leveldb.DB, create_if_missing=True)
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
        yield from (x[1] for x in items(self, *args, **kwargs))
        
        
        # values = functools.partial(leveldb.DB.iterator, include_key=False)

else:
    raise ImportError("bad mode: {}".format(_mode))