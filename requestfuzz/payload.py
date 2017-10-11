#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future import utils as six

import copy

try:
    from typing import Callable
except:
    pass

from .utils import ensure_unicode


@six.python_2_unicode_compatible
class Payload(object):
    """
    用于保存payload的容器

    参数格式化占位符: [>name<]

    Args:
        content(str|bytes|unicode):
            字面意思, 可以包含格式化标记, 例如:
                "http://[>reqid<].hacker.com"
            格式化标记会在 .format() 中被替换

        pattern(str|bytes|unicode|Callable):
            阳性结果中出现的的pattern, 例如:
                "root:x:0:0:root:"
            允许传入自定义函数, 函数原型为:
                def match(self, resp) --> bool
                其中resp是对应的响应, 即 `requests.Response` 类

        places(tuple[str]):
            此payload应用的地方, 留空则为不限(有待增强)
            eg: ["path", "headers"]
            可选的值为: query data headers path (未来还会添加)

    Examples:
        Payload("/etc/password", "root:x:0:0:root:")
        Payload("[>ori_val<]@[>reqid<].hacker.com")  # 不包含pattern

    Warnings:
        在开发时不要改变参数顺序, 因为会直接传进来

    Notes:
        格式化标记参考:
            reqid:
                请求的全局ID, 一般格式为
                  [prefix][三个字母][序号][三个字母]
                例如: xce123frg 在openfuzz里直接作为特征串用
            ori_val:
                被污染的参数的原始值
                例如 id=233 中的 ori_val 就是 "233"
            url_no_path:
                没有path的url, 即url的前缀, 等效于 `fuzzable.Url.without_path`
                例如: http://cat.com
            # 有需要再继续添加

    """

    def __init__(self, content, pattern=None, places=None):
        self.content = content
        self.pattern = pattern  # pattern允许是函数
        self.places = places

    def format(self, **kwargs):
        """
        格式化payload, 并返回一个新的实例

        Args:
            **kwargs: 格式化参数

        Returns:
            Payload: 格式化后的新payload实例
        """
        new = copy.deepcopy(self)
        new._iformat(**kwargs)
        return new

    def _iformat(self, **kwargs):
        """就地格式化, 会修改自身"""
        _ctt = self.content
        for k, v in kwargs.items():

            # sentry #1868 #1884
            if v is None:
                v = ""
            elif isinstance(v, six.binary_type):  # sentry #1910
                try:
                    v = ensure_unicode(v)
                except UnicodeError:
                    v = ""
            elif not isinstance(v, six.text_type):
                v = str(v)

            _ctt = _ctt.replace("[>" + k + "<]", v)
        self.content = _ctt

    def __str__(self):
        return "{}<{}>".format(self.__class__.__name__, repr(self.content))

    def __repr__(self):
        if self.pattern:
            return "{}({}, {})".format(self.__class__.__name__, repr(self.content), repr(self.pattern))
        else:
            return "{}({})".format(self.__class__.__name__, repr(self.content))

    def __eq__(self, other):
        if isinstance(other, Payload):
            return other.content == self.content and other.pattern == self.pattern
        elif isinstance(other, six.string_types):
            return self.content == other
        else:
            return False

    @classmethod
    def build(cls, obj):
        """根据字符串等生成payload"""
        if isinstance(obj, Payload):
            return copy.deepcopy(obj)
        elif isinstance(obj, six.string_types):
            return cls(obj)
        elif isinstance(obj, (tuple, list)):
            return cls(*obj)
        elif isinstance(obj, dict):
            return cls(**obj)
