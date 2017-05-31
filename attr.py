#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals, division
import inspect
import collections

__version__ = (2017, 5, 30, 1)
__author__ = "Aploium<i@z.codes>"

DEFAULT_MAXDEPTH = 2
DEFAULT_MAXLEN = 2048
BASIC_PADDING_LENGTH = 4
PADDING_STEP = 4
DEFAULT_MASKED_KEYWORDS = ("secret", "password", "passwd", "token", "access_key")


def attributes(var,
               interested=None,
               maxlen=DEFAULT_MAXLEN,
               skip_private=True,
               max_depth=DEFAULT_MAXDEPTH,
               masked_keywords=DEFAULT_MASKED_KEYWORDS,
               from_dict=None,
               _padding=BASIC_PADDING_LENGTH,
               ):
    if _padding == BASIC_PADDING_LENGTH:
        output = "#### BEGIN ATTRIBUTES {} ####\n".format(type(var))
        output += "__str__: {}\n".format(repr(var))
    else:
        output = ""
    
    if from_dict is False or from_dict is None and not isinstance(var, collections.Mapping):
        from_dict = False
        names = dir(var)
    else:
        from_dict = True
        names = var.keys()
    
    half_len = maxlen // 2
    
    for name in names:
        if (skip_private and name.startswith("_")) or name.endswith("_"):
            continue
        
        if from_dict:
            subval = var[name]
        else:
            subval = getattr(var, name)
        
        type_str = str(type(subval))
        
        if inspect.ismethod(subval):
            subval_str = "<method>"
            nosub = True
        else:
            subval_str = repr(subval)
            nosub = False
        
        if masked_keywords:
            name_low = name.lower()
            for key in masked_keywords:
                if key in name_low:
                    subval_str = '***masked***'
                    nosub = True
                    break
        
        ori_subval_str = subval_str
        
        rec = False
        
        if len(subval_str) > maxlen:
            subval_str = "[OMITTED WARNING!] " \
                         + subval_str[:half_len] \
                         + " ###omit:{}### ".format(len(subval_str) - maxlen) \
                         + subval_str[half_len:]
        
        if interested is not None and max_depth and not nosub:
            for needle in interested:
                if needle in type_str or subval_str is True:
                    subval_str = attributes(
                        subval, maxlen=maxlen,
                        interested=interested,
                        max_depth=max_depth - 1,
                        _padding=_padding + PADDING_STEP,
                    )
                    rec = True
        
        if _padding:
            output += " " * _padding
        
        if not rec:
            output += "{name}: {value}\n".format(name=name, value=subval_str)
        else:
            output += "{name}: {value}\n{subvalues}".format(name=name, value=ori_subval_str, subvalues=subval_str)
    
    if _padding == BASIC_PADDING_LENGTH:
        output += "#### END ATTRIBUTES {} ####\n".format(type(var))
    
    return output


if __name__ == "__main__":
    import requests
    import time
    
    r = requests.get("https://www.baidu.com")
    
    start_time = time.time()
    print(attributes(r, interested=["RequestsCookieJar", "PreparedRequest"]))
    print("cost:", time.time() - start_time)
    
    print(attributes(r.headers))
    print(attributes({
        "password": "this should not be displayed",
        "PASSWD": "this should not be displayed",
    }))
