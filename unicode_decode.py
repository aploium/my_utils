#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import sys

try:
    import cchardet as chardet
except ImportError:
    try:
        import chardet
    except ImportError:
        pass

if sys.version_info[0] == 3:
    binary_type = bytes
    text_type = str
else:
    # noinspection PyUnresolvedReferences
    text_type = unicode
    binary_type = str


def unicode_decode(content):
    r"""
    用多种方式尝试解码二进制内容为unicode文本
    copy from `unicode_decode.py`

    :return: tuple(编码, 解码后的unicode)
    :rtype: (str, bytes)

    >>> unicode_decode("简体中文UTF8汉字".encode("utf8"))
    ('UTF-8', '简体中文UTF8汉字')
    >>> unicode_decode("简体中文GBK汉字".encode("gbk"))
    ('GB18030', '简体中文GBK汉字')
    >>> unicode_decode(b'\xfa\xfb\xfc')
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
        encoding = chardet.detect(content)["encoding"]
        return encoding, content.decode(encoding)
    except:
        pass
    
    raise UnicodeError("unable to decode {}".format(repr(content[:32])))


def ensure_unicode(content):
    if content is None:
        return content
    if isinstance(content, text_type):
        return content
    elif isinstance(content, binary_type):
        _, uni = unicode_decode(content)
        return uni
    return content
