# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six
import re

from orderedmultidict.orderedmultidict import omdict

if six.PY3:
    import collections
    from http.cookies import SimpleCookie
    from urllib import parse
else:
    # 这里不能用py2标准库的 SimpleCookie, 有很多坑
    from future.backports.http.cookies import SimpleCookie
    from future.backports.urllib import parse
    from future.moves import collections

from . import utils

REGEX_CHARSET = re.compile(r"charset=([\w-]+)", re.IGNORECASE)
_dummy_simple_cookie = SimpleCookie()


def to_querydict(data):
    if isinstance(data, QueryDict):
        return data
    if not data:
        return QueryDict()
    elif isinstance(data, six.string_types):
        # 这里 keep_blank_values 必须有, 否则会发生空参数的丢失
        # 详见: https://docs.python.org/3.6/library/urllib.parse.html#urllib.parse.parse_qsl
        data = utils.ensure_unicode(data)
        pairs = parse.parse_qsl(data, keep_blank_values=True)
        return QueryDict(pairs)
    elif utils.like_list(data) or utils.like_dict(data):
        return QueryDict(data)

    return data


class OrderedMultiDict(omdict):
    def items(self):
        return super(OrderedMultiDict, self).allitems()

    def __setitem__(self, key, value):
        if key not in self:
            super(OrderedMultiDict, self).__setitem__(key, value)
        else:
            self.inplace_set(key, value)

    def inplace_set(self, key, value):
        items = self.items()
        new_items = []
        _found_flag = False
        for _k, _v in items:
            if _k == key:
                if not _found_flag:
                    new_items.append((key, value))
                    _found_flag = True
            else:
                new_items.append((_k, _v))

        if not _found_flag:
            new_items.append((key, value))

        self.load(new_items)

    def update(self, values):
        if utils.like_dict(values):
            _values = values.items()
        else:
            _values = values
        for k, v in _values:
            self[k] = v


class HTTPHeaders(OrderedMultiDict):
    def _find_real_key(self, key):
        if six.PY2 and isinstance(key, six.binary_type):
            key = key.decode("UTF-8")

        for _k in self.keys():
            if _k.lower() == key.lower():
                return _k
        return key

    def __getitem__(self, key):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).__getitem__(key)

    def get(self, key, default=None):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).get(key, default)

    def __setitem__(self, key, value):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).__setitem__(key, value)

    def pop(self, key, default=None):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).pop(key, default)

    def add(self, key, value=None):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).add(key, value)

    def __contains__(self, key):
        key = self._find_real_key(key)
        return super(HTTPHeaders, self).__contains__(key)

    def update(self, other):  # TODO: 改成更加高性能的封装
        if hasattr(other, "items"):
            for k, v in other.items():
                self[k] = v

        else:
            for k, v in other:
                self[k] = v


class QueryDict(OrderedMultiDict):
    pass


@six.python_2_unicode_compatible
class Cookie(OrderedMultiDict):
    def __init__(self, data=None):

        super(Cookie, self).__init__()

        if data:
            self._load_cookies(data)

    def _load_cookies(self, data):
        """将str或dict或tuple-pair加载为cookie
        由于标准库的 load() 方法不支持list, 所以对list单独处理
        """
        if utils.like_list(data):
            data = collections.OrderedDict(data)

        simple_cookie = SimpleCookie(data)

        pairs = [(c.key, c.value) for c in simple_cookie.values()]

        pairs.sort(key=lambda item: self._find_key_pos(data, item[0]))

        self.update(pairs)

    @staticmethod
    def _find_key_pos(oridata, key):
        """查找某一key在原始cookie串中的位置"""
        if isinstance(oridata, six.string_types):
            for syntax in ("; {}=", ";{}=", " {}=", "{}="):
                pos = oridata.find(syntax.format(key))
                if pos != -1:
                    return pos
        elif utils.like_list(oridata):
            for index, (k, v) in enumerate(oridata):
                if k == key:
                    return index
        elif utils.like_dict(oridata):
            for index, (k, v) in enumerate(oridata.items()):
                if k == key:
                    return index
        else:  # 其他位置格式无法查找位置
            return 0

    def tostr(self):
        pairs = []

        for name, val in self.items():
            _, quoted_val = _dummy_simple_cookie.value_encode(val)
            pairs.append((name, quoted_val))

        output = "; ".join(
            "{}={}".format(k, v)
            for k, v in pairs
        )

        return output

    def __str__(self):
        return "{}".format(self.tostr())

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.tostr()))
