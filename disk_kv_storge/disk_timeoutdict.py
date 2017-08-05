#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals, division, print_function, absolute_import
import sys
import time
import json
import struct
import logging

logger = logging.getLogger(__name__)

try:
    from . import BaseDiskKV
except (ImportError, ValueError):
    # noinspection PyUnresolvedReferences
    from disk_kv_storge import BaseDiskKV

if sys.version_info[0] == 2:
    # noinspection PyUnresolvedReferences
    string_types = (str, unicode)
    # noinspection PyUnresolvedReferences
    integer_types = (int, long)
    # noinspection PyUnresolvedReferences
    text_type = unicode
    binary_type = (str, bytes, bytearray)
else:
    string_types = str
    integer_types = int
    text_type = str
    binary_type = (bytes, bytearray)

def pack_timestamp(value, timestamp=None):
    time_bytes = struct.pack("!d", timestamp or time.time())
    return time_bytes + value


def get_timestamp(b):
    return struct.unpack("!d", b[:8])[0]


def unpack_timestamp(b):
    timestamp = struct.unpack("!d", b[:8])[0]
    return b[8:], timestamp


# --------------------------------------------------------
def _key_encode(key):
    if isinstance(key, text_type):
        return key.encode("utf8")
    if isinstance(key, binary_type):
        return key
    if isinstance(key, integer_types):
        key = str(key)
    return key.encode("utf8")


def _key_decode(key):
    return key.decode("utf8")


# --------------------------------------------------------
try:
    import msgpack
except ImportError:
    logger.warning(
        "msgpack not found, please consider install msgpack (http://msgpack.org/) for serialization, "
        "it's better than json.  Fallback to builtin json for serialization"
    )
    
    def _value_encode(value):
        value = json.dumps(value)
        value = value.encode("UTF-8")
        value = pack_timestamp(value)
        return value
    
    
    def _value_decode(value):
        value = unpack_timestamp(value)[0]
        value = value.decode("UTF-8")
        value = json.loads(value)
        return value
else:
    def _value_encode(value):
        value = msgpack.dumps(value, use_bin_type=True)
        value = pack_timestamp(value)
        return value
    
    
    def _value_decode(value):
        value = unpack_timestamp(value)[0]
        value = msgpack.loads(value, encoding='UTF-8', use_list=False)
        return value


# --------------------------------------------------------
class DiskTimeoutDict(BaseDiskKV):
    """
    >>> import time
    >>> td = DiskTimeoutDict(1)
    >>> td["cat"] = "foobar"
    >>> assert td["cat"] == "foobar"
    >>> time.sleep(0.5)
    >>> td["dog"] = 42
    >>> assert td["cat"] == "foobar"
    >>> assert td.get("cat") == "foobar"
    >>> assert td.get("non-exist", "a") == "a"
    >>> assert tuple(td.keys()) == ("cat", "dog")
    >>> assert tuple(td.values()) == ("foobar", 42)
    >>> assert tuple(td.items()) == (("cat","foobar"), ("dog",42))
    >>> assert len(td) == 2
    >>> assert td["dog"] == 42, list(td.items())
    >>> time.sleep(0.6)
    >>> assert "cat" not in td
    >>> assert td["dog"] == 42
    >>> time.sleep(0.5)
    >>> assert "dog" not in td
    >>> td["x"] = 1
    >>> del td["x"]
    >>> assert "x" not in td
    >>>
    >>> # test json storge
    >>> _dic = {"mon":[1, 2, 3, 4, {"cat": 1, b"binkey": "中文"}]}
    >>> td["monkey"] = _dic
    >>> assert td["monkey"] == _dic
    >>>
    >>> # test many keys
    >>> for i in range(10000): td[str(i)] = {"i_{}".format(i): i}
    >>> for i in range(10000): assert td[str(i)] == {"i_{}".format(i): i}
    >>> time.sleep(1.1)
    >>> for i in range(10000): assert str(i) not in td
    """
    
    def __init__(self, max_age, check_interval=None, **kwargs):
        super(DiskTimeoutDict, self).__init__(**kwargs)
        
        if check_interval is None:
            check_interval = max_age / 10.0
        
        self.max_age = max_age
        self.check_interval = check_interval
        
        self.next_checkpoint = time.time() + self.check_interval
    
    def __getitem__(self, key):
        if self.next_checkpoint < time.time():
            self.remove_expired()
        return super(DiskTimeoutDict, self).__getitem__(key)
    
    def remove_expired(self):
        expired_key = []
        now = time.time()
        for k in self.keys(decode=False):
            value = self.rawget(k)
            tiemstamp = get_timestamp(value)
            if tiemstamp + self.max_age < now:
                expired_key.append(k)
        
        for k in expired_key:
            self.delete(k, decode=False)
        
        self.next_checkpoint = now + self.check_interval
        
        return len(expired_key)
    
    key_encode = staticmethod(_key_encode)
    key_decode = staticmethod(_key_decode)
    value_encode = staticmethod(_value_encode)
    value_decode = staticmethod(_value_decode)
