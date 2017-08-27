# coding=utf-8
"""
对原始HTTP请求的修改、编解码、转换


Requirements:
    future
    six
    requests
    bottle
    orderedmultidict

Compatible Interpreters:
    CPython 3.4/3.5/3.6+
    CPython 2.7
    Jython 2.7
"""
# --------------- 以下代码用于提供py2/py3/Jython兼容 ---------------
from __future__ import absolute_import, division, print_function, unicode_literals
# from future.builtins import *
import six
from future import standard_library

try:
    standard_library.install_aliases()
except:
    _future_standard_library_load_success = False
else:
    _future_standard_library_load_success = True

try:
    from future.backports.http.server import BaseHTTPRequestHandler
except:
    from BaseHTTPServer import BaseHTTPRequestHandler

from future.backports.http.cookies import SimpleCookie
from future.backports.urllib import parse
import platform

IS_JYTHON = platform.python_implementation() == "Jython"
# --------------- END COMPATIBLE LAYER ---------------

from io import BytesIO
import re
import json
import cgi
import copy
from collections import OrderedDict, Mapping

import requests
from bottle import MultiDict, FileUpload
from orderedmultidict.orderedmultidict import omdict

try:
    import cchardet
except ImportError:
    try:
        import chardet as cchardet
    except ImportError:
        pass

REGEX_CHARSET = re.compile(r"charset=([\w-]+)", re.IGNORECASE)


def extract_charset(content_type):
    if not content_type:
        return None
    m = REGEX_CHARSET.search(content_type)
    if m is None:
        return None
    else:
        return m.group(1)


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
    if isinstance(content, six.text_type):
        return content
    else:
        _, uni = unicode_decode(content)
        return uni


def _parse_qsl(qsl):
    pairs = parse.parse_qsl(qsl)
    dic = OrderedMultiDict(pairs)
    
    return dic


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


def make_netloc(host, scheme="http", port=None):
    if scheme == "https" and port in (None, 443) \
            or scheme == "http" and port in (None, 80):
        return host
    else:
        return "{}:{}".format(host, port)


class OrderedMultiDict(omdict):
    # def __init__(self, *a, **k):
    #     self.dict = OrderedDict((k, [v]) for (k, v) in OrderedDict(*a, **k).items())
    
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


class HTTPHeaders(OrderedMultiDict):
    def _find_real_key(self, key):
        if six.PY2 and not isinstance(key, six.text_type):
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


class BareRequest(BaseHTTPRequestHandler):
    def __init__(self, request_bin, scheme="http", real_host=None, port=None):
        self.rfile = BytesIO(request_bin)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()  # 这里会把header都读取掉
        self.body = self._load_body()  # header之后的内容是body
        
        # 转换headers
        self.headers = self._load_ordered_headers()
        
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
        self.real_host = real_host or self.host
        if port:
            self.port = port
        elif scheme == "https":
            self.port = 443
        else:
            self.port = 80
    
    def _load_ordered_headers(self):
        """获取和原始顺序一样的headers, 特别是为蛋碎的jython准备的"""
        
        if IS_JYTHON:
            _raw = self.raw.lower()
            
            def _header_pos(kv):
                _name = kv[0].encode("UTF-8").lower()
                
                for needle in (
                                b'\n' + _name + b': ',
                                b'\r' + _name + b': ',
                                b'\n' + _name + b':',
                                _name + b': ',
                                _name + b':',
                ):
                    pos = _raw.find(needle)
                    if pos != -1:
                        return pos
                
                return 99999999  # 没找到
            
            headers = [(ensure_unicode(k), ensure_unicode(v)) for k, v in self.headers.items()]
            
            # 按原来的顺序排序
            headers.sort(key=_header_pos)
            
            return HTTPHeaders(headers)
        
        else:
            return HTTPHeaders(self.headers.items())
    
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
        return _parse_qsl(self.query_string)
    
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
        return _parse_qsl(self.text)
    
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
        environ = {
            "QUERY_STRING": self.query_string,
            "REQUEST_METHOD": self.method,
            "CONTENT_TYPE": self.content_type,
            "CONTENT_LENGTH": self.content_length,
        }
        fs = cgi.FieldStorage(
            fp=BytesIO(self.body), headers=self.headers,
            environ=environ, keep_blank_values=True,
        )
        data = fs.list or []
        post = OrderedMultiDict()
        for item in data:  # type: cgi.FieldStorage
            if item.filename:
                post[item.name] = item
            else:
                post[item.name] = item.value
        return post
    
    @property
    def files(self):
        """
        
        Returns:
            dict[str, cgi.FieldStorage] | OrderedMultiDict: 文件
        """
        files = OrderedMultiDict()
        for name, item in self.POST.items():
            if isinstance(item, cgi.FieldStorage):
                files[name] = item
        return files
    
    @property
    def cookies(self):
        _cookie_str = self.headers.get('Cookie', '')
        if six.PY2:
            _cookie_str = _cookie_str.decode("UTF-8")
        simple_cookies = SimpleCookie(_cookie_str)
        pairs = [(c.key, c.value) for c in simple_cookies.values()]
        if six.PY2:
            # py2中, SimpleCookie是会丢失顺序的, 所以需要手工进行一次重排
            pairs.sort(key=lambda item: _cookie_str.find("{}=".format(item[0])))
        return OrderedMultiDict(pairs)
    
    @property
    def params(self):
        """同时包含GET和POST的内容"""
        params = OrderedMultiDict()
        for key, value in self.query.items():
            params[key] = value
        for key, value in self.POST.items():
            params[key] = value
        return params
    
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
        return self.headers.get("Host", "")
    
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
        return parse.urlunsplit((self.scheme, self.netloc, self.path, self.query_string, ""))
    
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
        if "Cookie" in _headers:
            del _headers["Cookie"]
        if "Content-Length" in _headers:
            del _headers["Content-Length"]
        return {
            "method": self.method,
            "url": self.url_no_query,
            "params": self.query,
            "data": self.body,
            "headers": _headers,
            "cookies": self.cookies,
        }
    
    def send(self, session=None, verify=False, **kwargs):
        session = session or requests.Session()
        req = self.to_requests()
        req["verify"] = verify
        req.update(kwargs)
        return session.request(**req)
    
    @classmethod
    def build(cls, old=None,  # TODO: 拆分此函数
              method=None, protocol=None,
              path=None, query=None,
              data=None, json=None, files=None,
              headers=None, cookies=None,
              host=None,
              real_host=None, port=None, scheme=None,
              line_sep=None,
              ):
        """
        组装新的BareRequest
        
        See Also:
            `test_build_modified`
        
        Args:
            old (BareRequest): 已有的对象
        Returns:
            BareRequest
        """
        
        _modify_cookies = cookies is not None
        _modify_url_no_query = any((scheme, host, real_host, port, path))
        url_no_query = None
        
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
        scheme = scheme if scheme is not None else "http"
        path = path if path is not None else "/"
        real_host = real_host or host
        netloc = make_netloc(real_host, scheme=scheme, port=port)
        headers_copy = copy.deepcopy(headers)
        line_sep = line_sep if line_sep is not None else b'\r\n'
        if _modify_url_no_query or not url_no_query:
            # 发生了修改, 必须重新组装
            url_no_query = parse.urlunsplit((scheme, netloc, path, "", ""))
        
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
            headers_copy["Cookie"] = fake_req.headers["Cookie"]
        if fake_req.headers.get("Content-Length"):
            headers_copy["Content-Length"] = fake_req.headers["Content-Length"]
        if fake_req.headers.get("Transfer-Encoding"):
            headers_copy["Transfer-Encoding"] = fake_req.headers["Transfer-Encoding"]
        
        # PreparedRequest 可能会改变Content-Type
        _new_content_type = fake_req.headers.get("Content-Type", "")
        if _new_content_type and _new_content_type not in headers_copy.get("Content-Type", ""):
            headers_copy["Content-Type"] = _new_content_type
        
        # 写host
        if host and host != headers_copy.get("Host"):
            headers_copy["Host"] = host
        
        # 写入headers
        for name, value in headers_copy.items():
            _line = "{}: {}".format(name, value)
            req += _line.encode("UTF-8") + line_sep
        # headers结束
        
        req += line_sep
        
        # -------- 构建body -----------
        _body = fake_req.body  # 读取 PreparedRequest 中的body
        if _body:
            if isinstance(_body, six.string_types):
                _body = _body.encode("UTF-8")  # TODO: 根据header来检测编码
            req += _body
        
        # -------- 构建新的 BareRequest --------
        new_bare_req = cls(req, real_host=real_host,
                           scheme=scheme, port=port, )
        
        # 返回
        return new_bare_req


# ----------------------------------------------------------------
# -----------------------  BEGIN TESTS ---------------------------
# ----------------------------------------------------------------

def test_decode_post():
    request_bin = b'''POST /index.html?fromSite=-2&fromSite=another&appName=cat HTTP/1.1
Host: www.example.com
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0
Accept: undefined
Accept-Language: zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3
Accept-Encoding: gzip, deflate, br
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: http://www.example.com/referer
Content-Length: 81
Cookie: t=qwertyuiop; _uab_collina=1501125267079; cna=zxcvbnm; _umdata=A502B1276E
Connection: close

loginId=abcdef.io&loginId=another-loginId&appName=cat&appEntrance=cat&bizParams=c'''
    request = BareRequest(request_bin, real_host="example.com")
    assert request.method == request.command == "POST"
    # header大小写不敏感
    assert request.headers["accept"] == "undefined"
    assert request.headers["Accept"] == "undefined"
    # 保证cookies的顺序和值和原始一样
    assert tuple(request.cookies.items())[:3] == (
        ('t', 'qwertyuiop'),
        # ('t', 'anothert'),
        ('_uab_collina', '1501125267079'),
        ('cna', 'zxcvbnm'),
    ), request.headers.items()
    
    assert request.host == "www.example.com"
    assert request.text[:16] == 'loginId=abcdef.i'
    assert request.real_host == "example.com"
    assert request.is_json is False
    assert request.is_form is True
    # 保证forms, 并且支持相同value多次出现
    assert tuple(request.forms.items())[:4] == (('loginId', 'abcdef.io'),
                                                ('loginId', 'another-loginId'),
                                                ('appName', 'cat'),
                                                ('appEntrance', 'cat'),)
    assert request.POST == request.forms  # 在本例情况下两者相同
    assert request.raw == request_bin
    assert request.content_length == 81
    assert request.user_agent == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0"
    assert request.is_xhr is True
    assert request.query_string == "fromSite=-2&fromSite=another&appName=cat"
    assert request.body == b'loginId=abcdef.io&loginId=another-loginId&appName=cat&appEntrance=cat&bizParams=c'
    # 保证顺序, 并支持重复
    assert tuple(request.query.items()) == (
        ('fromSite', '-2'),
        ('fromSite', 'another'),
        ('appName', 'cat'),
    )
    assert tuple((k.lower(), v) for k, v in request.headers.items())[:9] == (
        ('host', 'www.example.com'),
        ('user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0'),
        ('accept', 'undefined'),
        ('accept-language', 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3'),
        ('accept-encoding', 'gzip, deflate, br'),
        ('content-type', 'application/x-www-form-urlencoded; charset=UTF-8'),
        ('x-requested-with', 'XMLHttpRequest'),
        ('referer', 'http://www.example.com/referer'),
        ('content-length', '81'),
    )
    
    return request


def test_decode_get():
    request_bin = b"""GET /get?cat=1&dog=2 HTTP/1.1
Accept: text/html
Accept-Encoding: gzip, deflate
Connection: keep-alive
Host: httpbin.org
User-Agent: HTTPie/0.9.9
X-Needle: uCX6YrzPpTmax

"""
    
    r = BareRequest(request_bin)
    
    assert r.raw == request_bin
    assert r.host == "httpbin.org"
    assert tuple(r.query.items()) == (("cat", "1"), ("dog", "2"))
    assert r.user_agent == "HTTPie/0.9.9"
    
    return r


def test_decode_multipart():
    request_bin = b"""POST /post?cat=1&dog=2 HTTP/1.1
Host: httpbin.org
Content-Length: 296
User-Agent: http_clay/1.0
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryEW35oPYWK6qwibcP
Accept: text/html
Accept-Language: zh-CN,zh;q=0.8
Cookie: JSESSIONID=A53DAC634D455E4D1F16829B7BD480F7
Connection: close

------WebKitFormBoundaryEW35oPYWK6qwibcP
Content-Disposition: form-data; name="upload"; filename="abc.txt"
Content-Type: text/plain

afasfafasfasfa
------WebKitFormBoundaryEW35oPYWK6qwibcP
Content-Disposition: form-data; name="caption"

aaaaa
------WebKitFormBoundaryEW35oPYWK6qwibcP--"""
    r = BareRequest(request_bin, real_host="httpbin.org")
    
    assert len(r.POST) == 2
    assert len(r.files) == 1
    
    f = r.files["upload"]
    assert isinstance(f, cgi.FieldStorage)
    assert r.POST["upload"].file.getvalue() == f.file.getvalue()
    assert f.file.getvalue() == b'afasfafasfasfa'
    assert f.outerboundary == b"----WebKitFormBoundaryEW35oPYWK6qwibcP"
    assert f.disposition == "form-data"
    assert f.name == "upload"
    assert f.filename == "abc.txt"
    assert f.type == "text/plain"
    
    assert r.POST["caption"] == "aaaaa"
    
    return r


def test_resend(req, pattern=b'<h1>Example Domain</h1>'):
    tor = req.to_requests()
    r = requests.request(**tor)
    assert pattern in r.content
    return r


def test_build_same(r):
    def _decode(v):
        if isinstance(v, six.binary_type):
            return v.decode("UTF-8")
        else:
            return v
    
    # --- 测试什么都不变的情况下与原有数据保持相同
    same = BareRequest.build(old=r)
    
    for attr in ("host", "body", "is_json", "is_form",
                 "GET", "POST", "raw", "headers", "cookies",
                 "query", "query_string"):
        values = {"old": _decode(getattr(r, attr)),
                  "new": _decode(getattr(same, attr)),
                  }
        
        if isinstance(values["old"], six.string_types) \
                or isinstance(values["old"], six.binary_type):
            values["old"] = values["old"].lower()
            values["new"] = values["new"].lower()
        
        try:
            assert values["old"] == values["new"], attr
        except:
            logger.error(repr(values["old"]))
            logger.error(repr(values["new"]))
            raise
    
    return same


def test_build_modified(r):
    """

    Args:
        r (BareRequest):
    """
    
    # headers需要复制一份出来才能修改, 其他不用
    h = copy.deepcopy(r.headers)
    h["Accept"] = "*/*"  # 修改已有的字段, 字段顺序保持不变, 下同
    h["Cat"] = "dog"  # 新字段, 会加在最后面, 下同
    
    cookies = r.cookies
    cookies["cna"] = "changed"
    cookies["nonexist"] = "bar"
    
    data = r.forms
    data["appName"] = "dog"
    data["nonexist"] = "bar"
    
    query = r.query
    query["appName"] = "abcdefg&"
    query["nonexist"] = "23333"
    
    new = BareRequest.build(
        # 以下所有字段都是可有可无的
        #   为了demo, 所以才全部写上了
        old=r,
        method="PUT",
        protocol="HTTP/1.0",
        path="/yet/another/path",
        query=query,
        data=data,  # data的用法和行为和requests等同
        # json=  # json和files 的用法也和requests一样
        headers=h,
        host="www.example.org",
        cookies=cookies,
        port=443,
        scheme="https",
    )
    
    logger.debug("new req:\n%s", new.raw.decode("UTF-8"))
    
    _newh = copy.deepcopy(new.headers)
    _oldh = copy.deepcopy(h)
    
    for _hname in ("Content-Length", "Content-Type", "Cookie"):
        if _hname not in _oldh:
            del _newh[_hname]
    # headers的顺序和值相同
    assert tuple(x.lower() for x in _newh.keys()) == tuple(x.lower() for x in _oldh.keys())
    for _hname in ("Cookie", "Content-Length", "Host"):
        if _hname in _newh:
            del _newh[_hname]
            del _oldh[_hname]
    assert tuple(_newh.values()) == tuple(_oldh.values())
    
    assert new.port == 443
    assert new.real_host == r.real_host
    assert new.host == "www.example.org"
    assert new.path == "/yet/another/path"
    assert new.protocol == "HTTP/1.0"
    assert new.scheme == "https"
    assert new.method == "PUT"
    assert len(new.body) == new.content_length
    assert tuple(new.forms.items()) == tuple(data.items())
    assert tuple(new.query.items()) == tuple(query.items())
    assert dict(new.cookies.items()) == dict(cookies.items())
    
    return new


if __name__ == "__main__":
    try:
        import err_hunter
        
        err_hunter.colorConfig("DEBUG")
        logger = err_hunter.getLogger()
    except:
        import logging
        
        logging.basicConfig(level="DEBUG")
        logger = logging.getLogger(__name__)
    
    r = test_decode_post()
    test_resend(r)
    test_build_same(r)
    
    rm = test_build_modified(r)
    test_resend(rm)
    
    r = test_decode_get()
    test_resend(r, b"uCX6YrzPpTmax")
    test_build_same(r)
    test_build_modified(r)
    
    r = test_decode_multipart()
    test_resend(r, b'"upload": "afasfafasfasfa"')
    
    logger.info("all tests passed!")
