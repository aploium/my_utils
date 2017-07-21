#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import time
import collections

__version__ = (1, 1, 0)


class TimeoutDict(collections.UserDict):
    """
    >>> import time
    >>> td = TimeoutDict(1)
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
    >>> assert td["dog"] == 42
    >>> time.sleep(0.6)
    >>> assert "cat" not in td
    >>> assert td["dog"] == 42
    >>> time.sleep(0.5)
    >>> assert "dog" not in td
    >>> td["x"] = 1
    >>> del td["x"]
    >>> assert "x" not in td
    """
    
    # noinspection PyMissingConstructor
    def __init__(self, max_age):
        assert max_age >= 0
        
        self.data = collections.OrderedDict()
        self.oldest_time = time.time()
        self.max_age = max_age
    
    def oldest_item(self, with_time=False):
        key, time_value = next(iter(self.data.items()))
        time_, value = time_value
        if with_time:
            return key, value, time_
        else:
            return key, value
    
    def check_expire(self):
        now = time.time()
        if not self.oldest_time \
                or now - self.oldest_time < self.max_age:
            return 0
        
        del_list = []
        for key, time_value in self.data.items():  # 从旧往前依次检查
            if now - time_value[0] > self.max_age:
                del_list.append(key)
            else:
                self.oldest_time = time_value[0]
                break
        else:  # 没有被break, 所有key都被清空, 清零oldest_time
            self.oldest_time = time.time()
        
        for key in del_list:
            del self.data[key]
        
        return len(del_list)
    
    def __getitem__(self, key):
        self.check_expire()
        
        return super(self.__class__, self).__getitem__(key)[1]
    
    def __contains__(self, key):
        self.check_expire()
        
        return super(self.__class__, self).__contains__(key)
    
    def __delitem__(self, key):
        self.check_expire()
        super(self.__class__, self).__delitem__(key)
    
    def __len__(self):
        self.check_expire()
        return super(self.__class__, self).__len__()
    
    def keys(self):
        self.check_expire()
        return super(self.__class__, self).keys()
    
    def values(self):
        self.check_expire()
        return (x[1] for x in self.data.values())
    
    def items(self):
        self.check_expire()
        return ((k, v[1]) for k, v in self.data.items())
    
    def __setitem__(self, key, item):
        super(self.__class__, self).__setitem__(key, (time.time(), item))
