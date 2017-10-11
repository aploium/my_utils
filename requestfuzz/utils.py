#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

import collections

from tldextract import TLDExtract

try:
    import cchardet
except ImportError:
    try:
        import chardet as cchardet
    except ImportError:
        pass


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
        encoding = cchardet.detect(content)["encoding"]
        return encoding, content.decode(encoding)
    except:
        pass

    raise UnicodeError("unable to decode {}".format(repr(content[:32])))


def ensure_unicode(content):
    if content is None:
        return content
    if isinstance(content, six.text_type):
        return content
    else:
        _, uni = unicode_decode(content)
        return uni


def make_netloc(host, scheme="http", port=None):
    if not port \
            or scheme == "https" and (not port or port == 443) \
            or scheme == "http" and (not port or port == 80):
        return host
    else:
        return "{}:{}".format(host, port)


def like_dict(obj):
    """判断一个对象是否像是dict"""
    if isinstance(obj, (dict, collections.Mapping)):
        return True
    return hasattr(obj, "__getitem__") and hasattr(obj, "items")


def like_list(obj):
    """判断一个对象是否像是list, 不含str

    注意:
        由于不存在list和tuple的特有方法 (相对于dict和str),
        即
            >>> attr = lambda x: set(dir(x))
            >>> (attr([])&attr(tuple())).difference(attr({})|attr(""))
            set()

        是空集
        所以无法可靠地判断一个自定义对象是否是list-like
    """
    if isinstance(obj, (tuple, list)):
        return True
    elif isinstance(obj, six.string_types):
        return False
    elif isinstance(obj, collections.Sequence):
        return True
    try:
        return hasattr(obj, "__getitem__") and hasattr(obj, "index")
    except:
        return False


def is_ip_address(address):
    if not isinstance(address, six.string_types):
        return False

    parts = address.split(".")
    if len(parts) != 4:
        return False

    for item in parts:
        if not item.isdigit():
            return False

        if not 0 <= int(item) <= 255:
            return False

    return True


def extract_root_domain(domain):
    """
    获取根域名
    # copied form w3af.core.data.parsers.doc.url.URL#get_root_domain
    """
    # An IP address has no 'root domain'
    if is_ip_address(domain):
        return domain
    extract = TLDExtract(fallback_to_snapshot=True)
    extract_result = extract(domain)
    return '%s.%s' % (extract_result.domain, extract_result.suffix)
