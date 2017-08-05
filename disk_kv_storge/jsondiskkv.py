#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals, division, print_function, absolute_import
import logging
import sys

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

try:
    import msgpack
except ImportError:
    logger.warning("msgpack not found, please consider install msgpack(http://msgpack.org/) for serialization, "
                   "it's better than json.  Fallback to builtin json for serialization")


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
    
    import json
    
    
    def _value_encode(value):
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    
    
    def _value_decode(value):
        return json.loads(value.decode("utf-8"))
else:
    def _value_encode(value):
        return msgpack.dumps(value, use_bin_type=True)
    
    
    def _value_decode(value):
        return msgpack.loads(value, encoding='utf-8')


# -------------------------
class JsonDiskKV(BaseDiskKV):
    """
    >>> td = JsonDiskKV()
    >>> td["cat"] = "foobar"
    >>> assert td["cat"] == "foobar"
    >>> td["dog"] = 42
    >>> assert td["cat"] == "foobar"
    >>> assert td.get("cat") == "foobar"
    >>> assert td.get("non-exist", "a") == "a"
    >>> assert tuple(td.keys()) == ("cat", "dog")
    >>> assert tuple(td.values()) == ("foobar", 42)
    >>> assert tuple(td.items()) == (("cat","foobar"), ("dog",42))
    >>> assert len(td) == 2
    >>> assert td["dog"] == 42, list(td.items())
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
    """
    
    key_encode = staticmethod(_key_encode)
    key_decode = staticmethod(_key_decode)
    value_encode = staticmethod(_value_encode)
    value_decode = staticmethod(_value_decode)
