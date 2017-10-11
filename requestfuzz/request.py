#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six
import requests
import re
import copy
import collections

try:
    from urllib import parse
except ImportError:
    from future.backports.urllib import parse

from . import utils
from .datastructure import (
    OrderedMultiDict, QueryDict, HTTPHeaders, Cookie, to_querydict)
from .url import Url
from .recursive_parse import parse_multipart, split_multipart


# 注意: 这个 import 实际在此文件末尾, 以避免冲突
# from .bare import BareLoader

def merge_data(old, new, base=OrderedMultiDict):
    if not old:
        _old = base()
    else:
        _old = copy.deepcopy(old)
    if isinstance(old, tuple):
        _old = list(old)

    if utils.like_list(old):
        _old.extend(new)
        return _old

    elif utils.like_dict(old):
        _old.update(new)
        return _old

    else:
        return new


@six.python_2_unicode_compatible
class FuzzableRequest(object):  # TODO: 需要一个统一的 data 类
    """
    对http请求进行解析、修改的基础组件

    Args:
        meta(dict): 在meta中允许以dict形式存储少量额外信息
        bare(bytes): 裸包, 仅做存储使用
        plugins(list): 启用的插件, 例如
                         csrf、自动模拟浏览器头、移除无用参数等
                         基类都是 `plugin_base.FzPluginBase`
                       注意传入的是插件的类而不是实例
    """
    DEFAULT_PLUGINS = []

    def __init__(self, url,
                 method=None, protocol="HTTP/1.1",
                 data=None, json=None, files=None,
                 headers=None, cookies=None,
                 bare=None,
                 meta=None,
                 plugins=None,
                 ):

        self.plugins = []
        self.headers = HTTPHeaders(headers or [])
        self.protocol = utils.ensure_unicode(protocol)
        self.method = utils.ensure_unicode(method) if method else "GET"
        self.bare = bare
        self.meta = meta or {}

        self._url = Url(url)

        # 从str或dict加载cookie
        self.cookies = Cookie(cookies)

        self.data, self.json, self.files = self.prepare_data(
            data, json, files, self.content_type)

        # 初始化插件
        plugins = plugins or self.DEFAULT_PLUGINS
        if plugins:
            for plugin_class in plugins:
                _plg = plugin_class(self)
                self.plugins.append(_plg)

        self._event("init_complete")

    # ----------- 下面是对 self.url 的简单映射 ---------
    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = Url(value)

    @property
    def scheme(self):
        return self.url.scheme

    @scheme.setter
    def scheme(self, value):
        self.url.scheme = value

    @property
    def host(self):
        return self.url.host

    @host.setter
    def host(self, value):
        self.url.host = value

    @property
    def scheme(self):
        return self.url.scheme

    @scheme.setter
    def scheme(self, value):
        self.url.scheme = value

    @property
    def port(self):
        return self.url.port

    @port.setter
    def port(self, value):
        self.url.port = value

    @property
    def path(self):
        return self.url.path

    @path.setter
    def path(self, value):
        self.url.path = value

    @property
    def fragment(self):
        return self.url.port

    @fragment.setter
    def fragment(self, value):
        self.url.fragment = value

    @property
    def query(self):
        return self.url.query

    @query.setter
    def query(self, value):
        self.url.query = value

    @property
    def query_string(self):
        return self.url.query_string

    @property
    def netloc(self):
        """
        返回域名和端口, 默认端口自动省略
        等效于 urlsplit 的 .netloc

        Examples:
            "foo.com:8888"
            "bar.com"
        """
        return self.url.netloc

    # ----------- 简单的 property ---------

    @property
    def content_type(self):
        return self.headers.get("Content-Type", "")

    @property
    def bin_body(self):
        """返回二进制的body
        Returns:
            bytes
        """
        return self.to_bare_obj().body

    @bin_body.setter
    def bin_body(self, value):
        """设置data的原始值, 例如二进制值"""
        self.data = value

    # ----------- methods --------------

    def to_requests(self):
        """
        转换为供 `requests.request` 用的参数dict

        注意! 由于标准库的坑, to_requests() 的结果不能直接用
            json.dumps() 转化为json, 若有这样的需求, 请使用 .to_jsonable(

        Examples:
            import requests
            req_dict = fuzzable.to_requests()
            requests.request(**req_dict)
        """
        _headers = copy.deepcopy(self.headers)
        # if self.cookies:
        #     # 由于在py3.6以前的版本中, SimpleCookie是无序的,
        #     #   所以不得不手动设置header头
        #     _headers["Cookie"] = str(self.cookies)
        # elif "Cookie" in _headers:
        #     del _headers["Cookie"]

        if "Cookie" in _headers:
            del _headers["Cookie"]

        if "Content-Length" in _headers:
            del _headers["Content-Length"]
        return {
            "method": self.method,  # str
            "url": self.url.without_query,  # str
            "params": copy.deepcopy(self.query),  # dict
            "data": copy.deepcopy(self.data),  # dict or qsl or bin
            "headers": _headers,  # dict
            "cookies": copy.deepcopy(self.cookies),  # dict
            "json": copy.deepcopy(self.json),  # dict
            "files": copy.copy(self.files),  # dict
        }

    def to_jsonable(self):
        """
        转换为可以 json.dump 的dict
        注意! 键的顺序会错乱, 重复项也会丢失

        Examples:
            {
              "method": "POST",  # str
              "url": "http://cat.com:8080/foo.php?id=23&name=foo",  # str
              "params": {"id":"23", "name":"foo"},  # dict
              "data": {"fff":"aaa", "bbb":"ccc"},  # dict or qsl or bin
              "headers": ...,  # dict
              "cookies": ...,  # dict
              "json": ...,  # dict or None
              "files": ...,  # dict or None
            }
        """
        req_dict = self.to_requests()

        # 替换为完整url
        req_dict["url"] = str(self.url)

        for k in ("params", "headers", "cookies", "files"):
            req_dict[k] = dict(req_dict[k]) if req_dict[k] else {}

        if utils.like_dict(req_dict["data"]):
            req_dict["data"] = dict(req_dict["data"])

        return req_dict

    def to_bare_obj(self):
        """转换为 Bare 对象
        Returns:
            BareLoader
        """
        return BareLoader.from_fuzzable(self)

    def to_bare(self):
        """转换为socket级别的裸二进制请求体, 就跟抓包看到的那种一样"""
        return self.to_bare_obj().raw

    # noinspection PyTypeChecker
    def fork(self,
             method=None, protocol=None,
             path=None, query=None,
             data=None, json=None, files=None,
             headers=None, cookies=None,
             host=None,
             port=None, scheme=None,
             meta=None,
             ):
        """创建拷贝并以merge的形式更新某些值"""
        # 进行复制
        new = self.deepcopy()

        # 修改值
        new.merge(
            # 嘛虽然可以直接写 **kwargs, 不过出于辅助IDE补全提示的考虑
            #   还是这样繁琐地全部写出来了
            method=method, protocol=protocol,
            path=path, query=query,
            data=data, json=json, files=files,
            headers=headers, cookies=cookies,
            host=host,
            port=port, scheme=scheme,
            meta=meta,
        )

        return new

    def merge(self,
              method=None, protocol=None,
              path=None, query=None,
              data=None, json=None, files=None,
              headers=None, cookies=None,
              host=None,
              port=None, scheme=None,
              meta=None,
              ):
        """就地更新某些值, 对于dict-like的值, 以merge的方式修改"""
        if method: self.method = method
        if protocol: self.protocol = protocol
        if path: self.path = path
        if host: self.host = host
        if port: self.port = port
        if scheme: self.scheme = scheme

        data, json, files = self.prepare_data(data, json, files, self.content_type)

        # merge
        if meta: self.meta = merge_data(self.meta, meta, base=dict)
        if json: self.json = merge_data(self.json, json, base=dict)
        if files: self.files = merge_data(self.files, files, base=QueryDict)
        if headers: self.headers = merge_data(self.headers, headers, base=HTTPHeaders)
        if cookies: self.cookies = merge_data(self.cookies, cookies, base=Cookie)

        if data:
            self.data = merge_data(self.data, data, base=QueryDict)
        if query:
            query = to_querydict(query)
            self.query = merge_data(self.query, query, base=QueryDict)

    # --------------- complex ------------
    if six.PY2:
        def deepcopy(self):
            if not self.files:
                return copy.deepcopy(self)
            else:
                # 由于py2的deepcopy无法对 StringIO 进行,
                #   所以需要临时把files取出, 对其余部分进行deepcopy以后
                #   再重新把浅copy的files放进去
                # 这是线程不安全的, 不过因为访问非常不稀疏
                #   所以实际上是没问题的
                _files = self.files
                self.files = None
                new = copy.deepcopy(self)
                self.files = _files
                new.files = copy.copy(_files)
                return new
    else:
        def deepcopy(self):
            # py3完全没问题
            return copy.deepcopy(self)

    # -------------- private ------------
    def _event(self, event, *args, **kwargs):
        method = "on_{}".format(event)
        for plugin in self.plugins:
            getattr(plugin, method)(*args, **kwargs)

    # --------- magic method ----------

    def __str__(self):
        return "{}<{} {}>".format(self.__class__.__name__, self.method, self.url)

    __repr__ = __str__

    # --------- classmethod -----------
    @classmethod
    def from_bare(cls, bare, **kwargs):
        """
        从socket级别的二进制请求体生成 FuzzableRequest

        Args:
            bare(BareLoader|bytes): 裸二进制或 BareLoader
        """
        if not isinstance(bare, BareLoader):
            bare = BareLoader(bare)

        fz = bare.to_fuzzable(cls, **kwargs)
        return fz

    # --------- staticmethod ------------
    @staticmethod
    def prepare_data(data=None, json=None, files=None, content_type=None):
        """
        预处理请求数据

        Args:
            data (QueryDict|str|bytes):
            json (dict|str):
            files (dict[str, cgi.FieldStorage]):
            content_type (str):

        Returns:
            (QueryDict, dict, dict[str, cgi.FieldStorage]):
        """
        # 处理 multipart
        if content_type and content_type.startswith("multipart/") \
                and isinstance(data, six.string_types):
            _multipart = parse_multipart(data, content_type)
            # 把 _multipart 中的 form 部分和 files 部分分开存
            _forms, _files = split_multipart(_multipart)
            data = _forms
            if files:
                files = merge_data(files, _files)
            else:
                files = _files
        else:
            try:
                data = to_querydict(data)
            except:
                pass  # data就是二进制

        if isinstance(json, six.string_types):
            import json as libjson  # 两个 json 名字不能冲突
            json = libjson.loads(json)

        return data, json, files


from .bare import BareLoader
