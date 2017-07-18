#!/usr/bin/env python3
# coding=utf-8
import os
import sys
import platform
import functools

import import_file

_mode = None
NAME = None

if platform.system() == "Windows":
    _dirname = os.path.dirname(os.path.abspath(__file__))
    if sys.version_info[:2] == (3, 6):
        try:
            leveldb = import_file.import_file(os.path.join(_dirname, "leveldb_win_py36.pyd"), "leveldb")
        except Exception as e:
            raise ImportError(str(e))
        NAME = "pyleveldb_win_py36"
    
    elif sys.version_info[:2] == (2, 7):
        try:
            leveldb = import_file.import_file(os.path.join(_dirname, "leveldb_win_py27.pyd"), "leveldb")
        except Exception as e:
            raise ImportError(str(e))
        NAME = "pyleveldb_win_py27"
    else:
        raise ImportError("unsupported version")
    _mode = "pyleveldb"

else:
    try:
        import plyvel as leveldb
    except ImportError:
        import leveldb
        
        _mode = "pyleveldb"
        NAME = "pyleveldb_unix"
    else:
        _mode = "plyvel"
        NAME = "plyvel_leveldb_unix"

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
