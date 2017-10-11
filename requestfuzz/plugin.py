#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

import collections
import weakref

try:  # 供type hint使用
    from .request import FuzzableRequest
except:
    pass


class FzPluginBase(object):
    """
    用于以插件形式给 FuzzableRequest 添加额外功能
    插件允许以事件钩子的形式影响fz的行为

    现在只有1个钩子, 如果还有其他需求, 到时候再加

    Args:
        fz (FuzzableRequest): 关联的请求
    """

    def __init__(self, fz):
        """

        Args:
             fz (FuzzableRequest):
        """
        # 使用weakref以避免循环引用, 实际操作时和普通的没有区别
        self.fz = weakref.proxy(fz)

    def on_init_complete(self):
        """在fz初始化完成后被调用"""


class AutoHeader(FzPluginBase):
    """
    自动给请求添加浏览器中常见的缺失的头, 包括referer
    """
    DEFAULT_HEADERS = collections.OrderedDict([
        ('Accept-Encoding', "gzip, deflate"),
        ('Accept-Language', "zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2"),
        ('User-Agent',
         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"),
        ('Accept', "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"),
    ])

    def on_init_complete(self):
        for k, v in self.DEFAULT_HEADERS.items():
            if k not in self.fz.headers:
                self.fz.headers[k] = v
        self._set_referer()

    def _set_referer(self, force=False):
        if not force and "Referer" in self.fz.headers:
            return
        else:
            self.fz.headers["Referer"] = self.fz.url.tostr()


class AutoCleanParam(FzPluginBase):
    """自动移除无用的查询key, 例如 spm 之类的"""
    USELESS_PARM = [
        'spm', '_spm', '__preventCache', '_t',
        'timestamp', '_timestamp', '__timestamp',
        "_",
    ]

    def on_init_complete(self):
        for key in self.USELESS_PARM:
            if key in self.fz.query:
                del self.fz.query[key]
