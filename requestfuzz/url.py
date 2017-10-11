#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

from urllib import parse

from . import utils
from .datastructure import QueryDict, to_querydict


@six.python_2_unicode_compatible
class Url(object):
    """
    Url对象

    <scheme>://<netloc>/<path>?<query_string>#<fragment>

    Args:
        data (str|tuple): 可以传入url, 或一个五元组,
            即 urlsplit() 得到的五元组

    Args:
        scheme(str)      : "http"/"https"
        host(str)        : 不带端口号的host
        port(int)        : 端口
        path(str)        : 带有前导 / 的path
        fragment(str)    : url里 # 号后面的frag, 大部分情况下没有
        query(QueryDict) : 字典形式的 query

    Methods:
        filename         : property  url里的文件名  *允许赋值
        url              : property 完整的url  *允许赋值
        netloc           : property 带有端口号的, 即 host:port,
                            如果是默认端口则省略端口号
        query_string     : property 字符串形式的 query
        without_query    : property 不带query的url
        without_path     : property 不带path的url (自然也不带query)
        all_but_scheme   : property  url里除了scheme的部分
        path_qs          : property  path和query_string
        root_domain      : property  根域名
        ext              : property  扩展名

        tostr():      : 转换为完整的url

    See Also:
        `requestfuzz.tests.test_url`

    """

    def __init__(self, data):
        self._set_url(data)

    @property
    def netloc(self):
        """
        返回域名和端口, 默认端口自动省略
        等效于 urlsplit 的 .netloc

        Examples:
            "foo.com:8888"
            "bar.com"
        """
        return utils.make_netloc(self.host, self.scheme, self.port)

    @property
    def query_string(self):
        return parse.urlencode(self.query)

    @property
    def url(self):
        return self.tostr()

    @url.setter
    def url(self, data):
        self._set_url(data)

    @property
    def without_query(self):
        """
        返回不带query的url

        Examples:
            "http://foo.com:88/cat.html"
            "https://foo.com/dog.php"
        """
        return parse.urlunsplit((self.scheme, self.netloc, self.path, "", ""))

    @property
    def without_path(self):
        """
        返回不带path的url (自然也不带query)

        Examples:
            "http://foo.com:88"
            "https://bar.com"
        """
        return parse.urlunsplit((self.scheme, self.netloc, "", "", ""))

    @property
    def path_qs(self):
        """
        path和qs

        Examples
            <-- http://cat.com:8080/foo/dog.txt?q=1
            --> /foo/dog.txt?q=1
        """
        qs = self.query_string
        if qs:
            return "{}?{}".format(self.path, qs)
        else:
            return self.path

    @property
    def root_domain(self):
        """
        Get the root domain name.

        Examples:
            input: www.ciudad.com.ar
            output: ciudad.com.ar

            input: i.love.myself.ru
            output: myself.ru

        """
        return utils.extract_root_domain(self.host)

    @root_domain.setter
    def root_domain(self, value):
        """
        设置新的root domain
        通常用于伪造域名, 例如把 foo.com 改成 myfoo.com

        Examples:
            ori: http://foo.bar.com/abc
            new: monkey.com
            output: http://foo.monkey.com/abc
        """
        value = value.lstrip(".")  # 移除左边多余的点
        old_root = self.root_domain
        self.host = self.host[:-len(old_root)] + value

    @property
    def filename(self):
        """
        返回url路径中可能存在的文件名

        Examples:
            http://cat.com/foo/dog.txt --> dog.txt
        """
        return self.path[self.path.rfind("/") + 1:]

    @filename.setter
    def filename(self, filename):
        """
        设置url路径中的文件名

        Examples:
            >>> url = Url("http://cat.com/bar/dog.txt")
            >>> url.filename = "foo.jpg"
            >>> str(url)
            "http://cat.com/bar/foo.jpg"
        """
        self.path = self.path[:self.path.rfind("/") + 1] + filename

    @property
    def ext(self):
        """
        返回url文件名的扩展名, 返回值中带有点

        Examples:
            http://cat.com/foo/dog.txt --> .txt
        """
        filename = self.filename
        pos = filename.rfind('.')
        if pos == -1:
            return ""
        else:
            return filename[pos:]

    @property
    def all_but_scheme(self):
        """
        返回除了scheme以外url里所有东西

        Examples:
            <-- http://cat.com:8080/foo/dog.txt?q=1
            --> cat.com:8080/foo/dog.txt?q=1
        """
        # 这里产生的是类似这样的带有前导 // 的, 需要手动去掉它

        _with_slash = parse.urlunsplit(
            ("", self.netloc, self.path, self.query_string, self.fragment))
        return _with_slash[2:]

    def tostr(self):
        return parse.urlunsplit((self.scheme, self.netloc, self.path, self.query_string, self.fragment))

    def split(self):
        # noinspection PyArgumentList
        return parse.SplitResult(self.scheme, self.netloc, self.path, self.query_string, self.fragment)

    def _set_url(self, data):
        """根据url来更新对应的值, 一律覆盖旧的"""
        # 根据url解开一些参数
        sp = self._urlsplit(data)

        self.scheme = sp.scheme
        self.host = sp.hostname
        self.path = sp.path
        self.fragment = sp.fragment

        if sp.port:
            self.port = sp.port
        else:
            self.port = {"http": 80, "https": 443}.get(self.scheme, None)

        # 转换query
        query = sp.query
        self.query = to_querydict(query)

    def __str__(self):
        return self.tostr()

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.tostr()))

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url == other

    def __contains__(self, item):
        return item in self.url

    def __iter__(self):
        return iter(self.url)

    @staticmethod
    def _urlsplit(data):
        """

        Args:
            data (str|tuple)
        Returns:
            parse.SplitResult: 切分后的五元组
        """
        if utils.like_list(data):
            assert len(data) == 5
            # noinspection PyArgumentList
            return parse.SplitResult(*data)
        elif isinstance(data, six.string_types):
            data = utils.ensure_unicode(data)
            return parse.urlsplit(data)
        elif isinstance(data, Url):
            return data.split()
        else:
            raise TypeError("unknown type: {}, need str or tuple".format(type(data)))
