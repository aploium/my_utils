#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

import cgi
import copy
import json
from io import BytesIO

if six.PY3:
    from http.server import BaseHTTPRequestHandler
    from urllib import parse
else:
    from future.backports.http.server import BaseHTTPRequestHandler
    from future.backports.urllib import parse

import requests
from .utils import ensure_unicode, unicode_decode, make_netloc
from .datastructure import HTTPHeaders, Cookie, QueryDict, to_querydict
from .request import FuzzableRequest
from .url import Url
from .recursive_parse import parse_multipart, split_multipart


def _iter_chunked(stream, buffsize=32 * 1024):
    err = ValueError("Error while parsing chunked transfer body.")
    rn, sem, bs = b'\r\n', b';', b''
    while True:
        header = stream.read(1)
        while header[-2:] != rn:
            c = stream.read(1)
            header += c
            if not c or len(header) > buffsize:
                raise err

        size, _, _ = header.partition(sem)

        try:
            maxread = int(size.strip(), 16)
        except ValueError:
            raise err
        if maxread == 0:
            break
        buff = bs
        while maxread > 0:
            if not buff:
                buff = stream.read(min(maxread, buffsize))
            part, buff = buff[:maxread], buff[maxread:]
            if not part:
                raise err
            yield part
            maxread -= len(part)
        if stream.read(2) != rn:
            raise err


# 因为 bare 字段已经整合到 FuzzableRequest 中
#   所以 BareRequest 已经不需要, 出于兼容性, 在这里保留一个alias
#   ps: 将二进制转换为 FuzzableRequest 请使用 FuzzableRequest.from_bare()
BareRequest = FuzzableRequest


class BareLoader(BaseHTTPRequestHandler):
    def __init__(self, request_bin, scheme="http", real_host=None, port=None):
        self.rfile = BytesIO(request_bin)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()  # 这里会把header都读取掉
        self.body = self._load_body()  # header之后的内容是body

        # 转换headers
        self.headers = HTTPHeaders(self.headers.items())

        self._path = ensure_unicode(self.path)
        self.command = ensure_unicode(self.command)

        if self.raw_requestline.endswith(b"\r\n"):
            self.line_sep = b'\r\n'
        elif self.raw_requestline.endswith(b'\r'):
            self.line_sep = b'\r'
        else:
            self.line_sep = b'\n'

        sp = parse.urlsplit(self._path)
        self.path = sp.path
        self.query_string = sp.query

        self.scheme = scheme

        # 解决host中有端口的问题
        _host = self.headers.get("Host", "").split(":")
        if len(_host) == 2 and port is None:
            port = int(_host[1])

        self.real_host = real_host or self.host
        if port:
            self.port = port
        elif scheme == "https":
            self.port = 443
        else:
            self.port = 80

    def send_error(self, code, message=None, explain=None):
        """此方法无用, 仅系统调用所需"""
        self.error_code = code
        self.error_message = message

    def _load_body(self):
        if not self.chunked:
            # 不是chunked的话直接读就行
            return self.rfile.read()
        else:
            # chunked的话需要一部分一部分读然后组装
            return b"".join(_iter_chunked(self.rfile))

    @property
    def query(self):
        return to_querydict(self.query_string)

    GET = query  # alias

    @property
    def protocol(self):
        return self.request_version

    @property
    def method(self):
        return self.command

    @property
    def content_type(self):
        return self.headers.get("Content-Type", "")

    @property
    def content_length(self):
        return int(self.headers.get("Content-Length", -1))

    @property
    def text(self):
        encoding, text = unicode_decode(self.body)
        return text

    @property
    def is_json(self):
        return "/json" in self.content_type

    @property
    def is_form(self):
        return "www-form-urlencoded" in self.content_type

    @property
    def json(self):
        return json.loads(self.text)

    @property
    def forms(self):
        if self.is_form:
            return to_querydict(self.text)
        else:
            return split_multipart(self.POST)[0]

    @property
    def xml(self):  # TODO: 写xml
        raise NotImplementedError()

    @property
    def POST(self):
        if self.is_form:
            return self.forms
        if self.is_json:
            return self.json

        # decode else, eg: multipart
        return parse_multipart(self.body, self.content_type)

    @property
    def files(self):
        """

        Returns:
            dict[str, cgi.FieldStorage] | OrderedMultiDict: 文件
        """
        return split_multipart(self.POST)[1]

    @property
    def cookies(self):
        _cookie_str = self.headers.get('Cookie', '')
        if six.PY2:
            _cookie_str = _cookie_str.decode("UTF-8")
        cookies = Cookie(_cookie_str)
        return cookies

    @property
    def raw(self):
        return self.rfile.getvalue()

    @property
    def chunked(self):
        return 'chunked' in self.headers.get("Transfer-Encoding", "")

    @property
    def is_xhr(self):
        return "XMLHttpRequest" == self.headers.get("X-Requested-With")

    @property
    def user_agent(self):
        return self.headers.get("User-Agent", "")

    @property
    def host(self):
        _host = self.headers.get("Host", "")
        if ":" in _host:
            _host = _host[:_host.find(":")]
        return _host

    @property
    def netloc(self):
        """
        返回域名和端口, 默认端口自动省略
        等效于 urlsplit 的 .netloc

        Examples:
            "foo.com:8888"
            "bar.com"

        """
        return make_netloc(self.real_host, scheme=self.scheme, port=self.port)

    @property
    def url(self):
        return Url(parse.urlunsplit((self.scheme, self.netloc, self.path, self.query_string, "")))

    @property
    def url_no_query(self):
        """
        返回不带query的url

        Examples:
            "http://foo.com:88/cat.html"
            "https://foo.com/dog.php"
        """
        return parse.urlunsplit((self.scheme, self.netloc, self.path, "", ""))

    @property
    def url_no_path(self):
        """
        返回不带path的url

        Examples:
            "http://foo.com:88"
            "https://bar.com"

        """
        return parse.urlunsplit((self.scheme, self.netloc, "", "", ""))

    def to_requests(self):
        """
        转换为供 `requests.request` 用的参数dict

        Examples:
            import requests
            req_dict = some_obj.to_requests()
            requests.request(**req_dict)

        Returns:
            Dict[str, str]:
        """
        _headers = copy.deepcopy(self.headers)

        if self.cookies:
            # 由于在py3.6以前的版本中, SimpleCookie是无序的,
            #   所以不得不手动设置header头
            _headers["Cookie"] = str(self.cookies)
        elif "Cookie" in _headers:
            del _headers["Cookie"]

        if "Content-Length" in _headers:
            del _headers["Content-Length"]
        return {
            "method": self.method,
            "url": self.url.without_query,
            "params": self.query,
            "data": self.body,
            "headers": _headers,
            # "cookies": self.cookies,
        }

    def send(self, session=None, verify=False, **kwargs):
        session = session or requests.Session()
        req = self.to_requests()
        req["verify"] = verify
        req.update(kwargs)
        return session.request(**req)

    def to_fuzzable(self, klass=FuzzableRequest, **kwargs):
        """

        Returns:
            FuzzableRequest
        """
        kw = {}

        if self.is_json:
            kw["json"] = self.json
        elif self.is_form:
            kw["data"] = self.forms
        else:  # 包含文件
            kw["data"] = self.forms
            kw["files"] = self.files

        kw.update(kwargs)

        bare_request = klass(
            self.url, method=self.method, protocol=self.protocol,
            headers=self.headers, cookies=self.cookies,
            bare=self.raw,
            **kw)

        bare_request.host = self.host

        return bare_request

    @classmethod
    def from_fuzzable(cls, fuzzable):
        """
        Args:
            fuzzable (FuzzableRequest):
        """
        kw = {}
        if hasattr(fuzzable, "bare"):
            kw["old_bin"] = fuzzable.bare

        return cls.build(
            method=fuzzable.method, protocol=fuzzable.protocol,
            path=fuzzable.path, query=fuzzable.query,
            headers=fuzzable.headers, cookies=fuzzable.cookies,
            host=fuzzable.host, port=fuzzable.port,
            data=fuzzable.data, json=fuzzable.json, files=fuzzable.files,
            scheme=fuzzable.scheme,
            **kw
        )

    @classmethod
    def build(cls, old=None, old_bin=None,  # TODO: 拆分此函数
              method=None, protocol=None,
              path=None, query=None,
              data=None, json=None, files=None,
              headers=None, cookies=None,
              host=None,
              real_host=None, port=None, scheme=None,
              line_sep=None,
              ):
        """
        组装新的BareLoader

        See Also:
            `test_build_modified`

        Args:
            old (BareLoader): 已有的对象
        Returns:
            BareLoader
        """

        _modify_cookies = bool(cookies)
        _modify_url_no_query = any((scheme, host, real_host, port, path))
        url_no_query = None

        if old and old_bin:
            raise ValueError("old and old_bin should not be specified both")

        if old_bin is not None:
            old = cls(old_bin)

        if old is not None:
            path = path or old.path
            query = query or old.query_string
            data = data if any((data, json, files)) else old.body
            headers = headers or old.headers
            cookies = cookies if cookies is not None else old.cookies
            real_host = real_host or old.real_host
            port = port or old.port
            scheme = scheme or old.scheme
            line_sep = line_sep or old.line_sep
            method = method or old.method
            host = host or old.host
            protocol = protocol or old.request_version
            url_no_query = old.url_no_query

        # 处理默认值
        scheme = ensure_unicode(scheme if scheme is not None else "http")
        path = ensure_unicode(path if path is not None else "/")
        real_host = ensure_unicode(real_host or host)
        if host:
            netloc = make_netloc(host, scheme=scheme, port=port)
        else:
            netloc = None
        real_netloc = make_netloc(real_host, scheme=scheme, port=port)
        headers_copy = copy.deepcopy(headers)
        line_sep = line_sep if line_sep is not None else b'\r\n'
        if _modify_url_no_query or not url_no_query:
            # 发生了修改, 必须重新组装
            url_no_query = parse.urlunsplit((scheme, real_netloc, path, "", ""))

        # 处理cookies
        if _modify_cookies:
            # 显式指定了cookies, 则删除掉headers里的cookies,
            #   否则requests会以headers里的cookies覆盖掉手动传入的
            if headers_copy and "Cookie" in headers_copy:
                del headers_copy["Cookie"]

        if headers_copy:
            # 删除会干扰 PreparedRequest 的头
            for _hname in ('Content-Length', 'Content-Type'):
                if _hname in headers_copy:
                    del headers_copy[_hname]

        # ----- 利用requests的工具来构建各种参数 -------
        fake_req = requests.PreparedRequest()
        fake_req.prepare(
            method=method, url=url_no_query,
            headers=headers_copy, params=query,
            cookies=cookies,
            data=data, files=files, json=json
        )

        req = b''

        # -----  构建第一行请求行 --------
        request_line = ""

        # method
        request_line += fake_req.method
        request_line += ' '

        # path_url
        request_line += fake_req.path_url
        request_line += " "  # 中间的空格

        # protocol
        if protocol is None:
            request_line += "HTTP/1.1"
        else:
            request_line += protocol

        # 写入第一行
        req += request_line.encode("UTF-8") + line_sep
        # -------- 第一行完成 ----------


        # -------- 构建headers ---------
        headers_copy = copy.deepcopy(headers)
        if _modify_cookies:
            # 如果指定了新cookie, 就重建cookie
            _cookie_obj = Cookie(cookies)
            headers_copy["Cookie"] = str(_cookie_obj)
        if fake_req.headers.get("Content-Length"):
            headers_copy["Content-Length"] = fake_req.headers["Content-Length"]
        if fake_req.headers.get("Transfer-Encoding"):
            headers_copy["Transfer-Encoding"] = fake_req.headers["Transfer-Encoding"]

        # PreparedRequest 可能会改变Content-Type
        _new_content_type = fake_req.headers.get("Content-Type", "")
        if _new_content_type and _new_content_type not in headers_copy.get("Content-Type", ""):
            headers_copy["Content-Type"] = _new_content_type

        # 写host, 实际上是netloc

        if netloc and netloc != headers_copy.get("Host"):
            headers_copy["Host"] = netloc

        # 写入headers
        for name, value in headers_copy.items():
            _line = "{}: {}".format(name, value)
            req += _line.encode("UTF-8") + line_sep
        # headers结束

        req += line_sep

        # -------- 构建body -----------
        _body = fake_req.body  # 读取 PreparedRequest 中的body
        if _body:
            if isinstance(_body, six.text_type):
                _body = _body.encode("UTF-8")  # TODO: 根据header来检测编码
            req += _body

        # -------- 构建新的 BareLoader --------
        new_bare_req = cls(req, real_host=real_host,
                           scheme=scheme, port=port, )

        # 返回
        return new_bare_req
