#!/usr/bin/env python3
# coding=utf-8
import os
import json
from io import open

engines = {}
best_engine = None

try:
    from disk_kv_storge import leveldb_engine
except ImportError:
    raise
else:
    best_engine = leveldb_engine
    engines[leveldb_engine.NAME] = leveldb_engine

engines["best"] = best_engine


class DiskKV:
    """
    
    >>> db = DiskKV("tempdb")
    >>> db.put(b"cat",b"dog")
    >>> db.put(b"cat1",b"dog1")
    >>> db.put(b"cat2",b"dog2")
    >>> db.put(b"cat3",b"dog3")
    >>> bytes(db.get(b"cat1"))
    b'dog1'
    >>> bytes(db.get(b"cat2"))
    b'dog2'
    >>> db.put(b"cat3",b"monkey")
    >>> bytes(db.get(b"cat3"))
    b'monkey'
    >>> assert frozenset([b"cat",b"cat1",b"cat2",b"cat3"]) == frozenset(bytes(x) for x in db.keys())
    >>> assert frozenset([b"dog",b"dog1",b"dog2",b"monkey"]) == frozenset(bytes(x) for x in db.values())
    >>> assert {b"cat":b"dog",b"cat1":b"dog1",b"cat2":b"dog2",b"cat3":b"monkey"} == {bytes(k):bytes(v) for k,v in db.items()}
    >>> db.close()
    >>> del db
    >>> pass
    >>> pass
    >>> pass
    >>> db2 = DiskKV("tempdb")
    >>> assert {b"cat":b"dog",b"cat1":b"dog1",b"cat2":b"dog2",b"cat3":b"monkey"} == {bytes(k):bytes(v) for k,v in db2.items()}
    """

    def __init__(self, db_folder, engine=None):
        self.db_folder = db_folder
    
        os.makedirs(self.db_folder, exist_ok=True)
    
        self._load_meta()
    
        if engine is None and "engine" in self.meta:
            engine = self.meta.get("engine")
        if engine is None:
            engine = engines["best"]
        elif isinstance(engine, str):
            engine = engines[engine]
    
        self.engine = engine
    
        self.meta["engine"] = self.engine.NAME
    
        if self.meta.get("data_path"):
            self.data_path = self.meta["data_path"]
        else:
            self.data_path = os.path.join(self.db_folder, "data")
    
        self.db = engine.open(self.data_path)
    
        self._save_meta()

    def _load_meta(self, meta_file=None):
        if meta_file is None:
            meta_file = os.path.join(self.db_folder, "meta.json")
    
        if os.path.exists(meta_file):
            meta = json.load(open(meta_file, "r", encoding="utf8"))
        else:
            meta = {}
        self.meta = meta
        return meta

    def _save_meta(self, meta_file=None):
        if meta_file is None:
            meta_file = os.path.join(self.db_folder, "meta.json")
    
        json.dump(self.meta, open(meta_file, "w", encoding="utf8"), indent=4)

    def __getitem__(self, item):
        value = self.engine.get(self.db, item)
    
        if value is None:
            raise KeyError("key {} not exist".format(value))
    
        return value
    
    def get(self, key):
        try:
            value = self[key]
        except KeyError:
            return None
    
        return bytes(value)
    
    def put(self, key, value):
        return self.engine.put(self.db, key, value)
    
    def delete(self, key):
        return self.engine.delete(self.db, key)
    
    def keys(self):
        return (bytes(x) for x in self.engine.keys(self.db))
    
    def values(self):
        return (bytes(x) for x in self.engine.values(self.db))
    
    def items(self):
        return ((bytes(k), bytes(v)) for k, v in self.engine.items(self.db))
    
    def close(self):
        return self.engine.close(self.db)

    __iter__ = keys
    __setitem__ = put

    def __len__(self):
        count = 0
        for _ in self.keys():
            count += 1
        return count

    def __contains__(self, item):
        try:
            value = self[item]
        except KeyError:
            return False
        else:
            return value is not None
