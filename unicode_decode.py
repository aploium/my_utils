#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import cchardet


def decode(content):
    r"""
    用多种方式尝试解码二进制内容为unicode文本
    
    :return: tuple(编码, 解码后的unicode)
    :rtype: (str, bytes)
    
    >>> decode("简体中文UTF8汉字".encode("utf8"))
    ('UTF-8', '简体中文UTF8汉字')
    >>> decode("简体中文GBK汉字".encode("gbk"))
    ('GB18030', '简体中文GBK汉字')
    >>> decode(b'\xfa\xfb\xfc')
    Traceback (most recent call last):
        ...
    UnicodeError: unable to decode b'\xfa\xfb\xfc'
    
    """
    try:
        return "UTF-8", content.decode("UTF-8")
    except:
        pass
    
    try:
        return "GB18030", content.decode("GB18030")
    except:
        pass
    
    try:
        encoding = cchardet.detect(content)["encoding"]
        return encoding, content.decode(encoding)
    except:
        pass
    
    raise UnicodeError("unable to decode {}".format(repr(content[:32])))
