#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import sys
import os
import json
import collections
import tempfile

engines = {}
best_engine = None

try:
    try:
        from . import leveldb_engine
    except (ImportError, ValueError):
        # noinspection PyUnresolvedReferences
        from disk_kv_storge import leveldb_engine
except ImportError:
    raise
else:
    best_engine = leveldb_engine
    engines[leveldb_engine.NAME] = leveldb_engine

engines["best"] = best_engine

if sys.version_info[0] == 2:
    # noinspection PyUnresolvedReferences
    str_type = (str, unicode)
else:
    str_type = str

def _text_open(file,mode):
    if sys.version_info[0] == 2:
        return open(file, mode)
    else:
        return open(file, mode, encoding="utf8")


class BaseDiskKV(collections.MutableMapping):
    def __init__(self, db_folder=None, engine=None, auto_delete=None, block_cache_size=8 * (2 << 20)):
        if db_folder is None:
            self.db_folder = tempfile.mkdtemp(prefix="{}_".format(self.__class__.__name__))
            if auto_delete is None:
                auto_delete = True
        else:
            self.db_folder = db_folder
            if auto_delete is None:
                auto_delete = False
        self.auto_delete = auto_delete
        
        if not os.path.exists(self.db_folder):
            os.makedirs(self.db_folder)
    
        self._load_meta()
    
        if engine is None and "engine" in self.meta:
            engine = self.meta.get("engine")
        if engine is None:
            engine = engines["best"]
        elif isinstance(engine, str_type):
            engine = engines[engine]
    
        self.engine = engine
    
        self.meta["engine"] = self.engine.NAME
    
        if self.meta.get("data_path"):
            self.data_path = self.meta["data_path"]
        else:
            self.data_path = os.path.join(self.db_folder, "data")

        self.db = engine.open(self.data_path, block_cache_size=block_cache_size)
    
        self._save_meta()

    def _load_meta(self, meta_file=None):
        if meta_file is None:
            meta_file = os.path.join(self.db_folder, "meta.json")
    
        if os.path.exists(meta_file):
            meta = json.load(_text_open(meta_file, "r"))
        else:
            meta = {}
        self.meta = meta
        return meta

    def _save_meta(self, meta_file=None):
        if meta_file is None:
            meta_file = os.path.join(self.db_folder, "meta.json")
    
        json.dump(self.meta, _text_open(meta_file, "w"), indent=4)
    
    def rawget(self, key):
        return self.engine.get(self.db, key)
    
    def __getitem__(self, key):
        if self.key_encode is not None:
            key = self.key_encode(key)
        
        value = self.rawget(key)
    
        if value is None:
            raise KeyError("key {} not exist".format(key))
        
        if self.value_decode is not None:
            return self.value_decode(value)
        else:
            return value
    
    def get(self, key, default=None):
        try:
            value = self[key]
        except KeyError:
            return default

        return value
    
    def put(self, key, value):
        if self.key_encode is not None:
            key = self.key_encode(key)
        if self.value_encode is not None:
            value = self.value_encode(value)
        return self.engine.put(self.db, key, value)
    
    def delete(self, key, decode=True):
        if self.key_encode is not None and decode:
            key = self.key_encode(key)
        return self.engine.delete(self.db, key)
    
    def keys(self, decode=True):
        if self.key_decode is not None and decode:
            return (self.key_decode(x) for x in self.engine.keys(self.db))
        else:
            return self.engine.keys(self.db)
    
    def values(self):
        if self.value_decode is not None:
            return (self.value_decode(x) for x in self.engine.values(self.db))
        else:
            return self.engine.values(self.db)
    
    def items(self):
        if self.key_decode is not None:
            if self.value_decode is not None:
                return ((self.key_decode(k), self.value_decode(v)) for k, v in self.engine.items(self.db))
            else:
                return ((self.key_decode(k), v) for k, v in self.engine.items(self.db))
        else:
            if self.value_decode:
                return ((k, self.value_decode(v)) for k, v in self.engine.items(self.db))
            else:
                return self.engine.items(self.db)
    
    def close(self):
        return self.engine.close(self.db)

    __iter__ = keys
    __setitem__ = put
    __delitem__ = delete

    def __len__(self):
        count = 0
        for _ in self.keys(decode=False):
            count += 1
        return count

    def __contains__(self, item):
        try:
            value = self[item]
        except KeyError:
            return False
        else:
            return value is not None
    
    def __del__(self):
        if self.auto_delete:
            self.close()
            del self.db
            import shutil
            shutil.rmtree(self.db_folder)
    
    key_encode = None
    key_decode = None
    value_encode = None
    value_decode = None


class DiskKV(BaseDiskKV):
    """
    >>> import tempfile
    >>> tempdb_path = tempfile.mkdtemp()
    >>> db = DiskKV(tempdb_path)
    >>> db.put(b"cat",b"dog")
    >>> db.put(b"cat1",b"dog1")
    >>> db.put(b"cat2",b"dog2")
    >>> db.put(b"cat3",b"dog3")
    >>> assert db.get(b"cat1") == b'dog1'
    >>> assert db.get(b"cat2") == b'dog2'
    >>> db.put(b"cat3",b"monkey")
    >>> assert db.get(b"cat3") == b'monkey'
    >>> assert frozenset([b"cat",b"cat1",b"cat2",b"cat3"]) == frozenset(x for x in db.keys())
    >>> assert frozenset([b"dog",b"dog1",b"dog2",b"monkey"]) == frozenset(x for x in db.values())
    >>> assert {b"cat":b"dog",b"cat1":b"dog1",b"cat2":b"dog2",b"cat3":b"monkey"} == {k:v for k,v in db.items()}
    >>> db.close()
    >>> del db
    >>>
    >>> db2 = DiskKV(tempdb_path)
    >>> assert {b"cat":b"dog",b"cat1":b"dog1",b"cat2":b"dog2",b"cat3":b"monkey"} == {k:v for k,v in db2.items()}
    """
    key_decode = bytes
    value_decode = bytes


try:
    from .disk_timeoutdict import DiskTimeoutDict
except (ImportError, ValueError):
    # noinspection PyUnresolvedReferences
    from disk_kv_storge.disk_timeoutdict import DiskTimeoutDict
