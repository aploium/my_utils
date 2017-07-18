#!/usr/bin/env python3
# coding=utf-8

try:
    from disk_kv_storge import leveldb_engine as engine
except ImportError:
    raise

name = engine.NAME


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
    """
    
    def __init__(self, dbpath):
        self.db = engine.open(dbpath)
    
    def get(self, key):
        return engine.get(self.db, key)
    
    def put(self, key, value):
        return engine.put(self.db, key, value)
    
    def delete(self, key):
        return engine.delete(self.db, key)
    
    def keys(self):
        return engine.keys(self.db)
    
    def values(self):
        return engine.values(self.db)
    
    def items(self):
        return engine.items(self.db)
    
    def close(self):
        return engine.close(self.db)
    
    def __iter__(self):
        return self.keys()
