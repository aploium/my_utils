# coding=utf-8
"""
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


def convert_headers(old, request_bin):
    pass


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


class BareRequest(BaseHTTPRequestHandler):
    def __init__(self, request_bin, scheme="http", real_host=None, port=None):
        self.rfile = BytesIO(request_bin)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()  # 这里会把header都读取掉
        self.body = self._load_body()  # header之后的内容是body
        
        # 转换headers
        self.headers = self._load_ordered_headers()
        
        self._path = self.path
        
        if self.raw_requestline.endswith(b"\r\n"):
            self.line_sep = b'\r\n'
        elif self.raw_requestline.endswith(b'\r'):
            self.line_sep = b'\r'
        else:
            self.line_sep = b'\n'
        
        if six.PY2:
            self._path = self._path.decode("UTF-8")
            # if not _future_standard_library_load_success:
            #     for key in tuple(self.headers.keys()):
            #         self.headers[key] = self.headers[key].decode("UTF-8")
        
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
            
            headers = list(self.headers.items())
            
            # 按原来的顺序排序
            headers.sort(key=_header_pos)
            
            return HTTPHeaders(headers)
        
        else:
            return HTTPHeaders(self.headers.items())
    
    def send_error(self, code, message=None, explain=None):
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
        for item in data:
            if item.filename:
                post[item.name] = FileUpload(item.file, item.name,
                                             item.filename, item.headers)
            else:
                post[item.name] = item.value
        return post
    
    @property
    def files(self):
        files = OrderedMultiDict()
        for name, item in self.POST.items():
            if isinstance(item, FileUpload):
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
        return 'chunked' in self.headers.get("transfer_encoding", "")
    
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
        return make_netloc(self.real_host, scheme=self.scheme, port=self.port)
    
    @property
    def url(self):
        return parse.urlunsplit((self.scheme, self.netloc, self.path, self.query_string, ""))
    
    @property
    def url_no_query(self):
        return parse.urlunsplit((self.scheme, self.netloc, self.path, "", ""))
    
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
        return dict(
            method=self.method,
            url=self.url_no_query,
            params=self.query,
            data=self.body,
            headers=_headers,
            cookies=self.cookies,
        )
    
    @classmethod
    def build(cls, old=None, method=None,
              path=None, query=None,
              body=None, protocol=None,
              headers=None, cookies=None,
              host=None,
              real_host=None, port=None, scheme=None,
              line_sep=None,
              ):
        """
        组装新的BareRequest
        
        See Also:
            test_build_modified
        
        Args:
            old (BareRequest): 已有的对象
        Returns:
            BareRequest
        """
        
        _modify_cookies = cookies is not None
        url_no_query = None
        
        if old is not None:
            path = path or old.path
            query = query or old.query_string
            body = body or old.body
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
        url_no_query = url_no_query or parse.urlunsplit((scheme, netloc, path, "", ""))
        line_sep = line_sep if line_sep is not None else b'\r\n'
        
        # 处理cookies
        if _modify_cookies:
            # 显式指定了cookies, 则删除掉headers里的cookies,
            #   否则requests会以headers里的cookies覆盖掉手动传入的
            if headers_copy and "Cookie" in headers_copy:
                del headers_copy["Cookie"]
        
        if headers_copy and 'Content-Length' in headers_copy:
            del headers_copy['Content-Length']
        
        # ----- 利用requests的工具来构建各种参数 -------
        fake_req = requests.PreparedRequest()
        fake_req.prepare(
            method=method, url=url_no_query,
            headers=headers_copy, params=query,
            cookies=cookies, data=body,
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
            headers_copy["Cookie"] = fake_req.headers["Cookie"]
        if fake_req.headers.get("Content-Length"):
            headers_copy["Content-Length"] = fake_req.headers["Content-Length"]
        
        for name, value in headers_copy.items():
            _line = "{}: {}".format(name, value)
            req += _line.encode("UTF-8") + line_sep
        # headers结束
        req += line_sep
        
        # -------- 构建body -----------
        _body = fake_req.body
        if isinstance(body, six.string_types):
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

def test_decode1():
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
    ), logger.error(request.headers.items())
    
    return request


def test_resend():
    import requests
    req = test_decode1()
    tor = req.to_requests()
    r = requests.request(**tor)
    assert b'<h1>Example Domain</h1>' in r.content
    return r


def test_build_same():
    def _decode(v):
        if isinstance(v, six.binary_type):
            return v.decode("UTF-8")
        else:
            return v
    
    r = test_decode1()
    
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
            logger.error(values["new"])
            logger.error(values["old"])
            raise
    
    return same


def test_build_modified():
    r = test_decode1()
    
    h = r.headers
    h["Accept"] = "*/*"
    h["Cat"] = "dog"
    
    cookies = r.cookies
    cookies["foo"] = "bar"
    cookies["t"] = "changed"
    
    new = BareRequest.build(
        old=r,
        headers=h,
        cookies=cookies,
        port=81,
        scheme="https",
    )
    
    _nh_cpy = copy.deepcopy(new.headers)
    _h_cpy = copy.deepcopy(h)
    del _nh_cpy["Cookie"]
    del _h_cpy["Cookie"]
    assert tuple(_nh_cpy.values()) == tuple(_h_cpy.values())
    
    assert new.port == 81
    assert new.real_host == "example.com"
    assert new.scheme == "https"
    
    try:
        assert dict(new.cookies.items()) == dict(cookies.items())
    except:
        logger.error(h["Cookie"])
        logger.error(cookies.items())
        logger.error(new.headers["Cookie"])
        logger.error(new.cookies.items())
        raise
    
    return new


if __name__ == "__main__":
    try:
        import err_hunter
        
        err_hunter.colorConfig()
        logger = err_hunter.getLogger()
    except:
        import logging
        
        logging.basicConfig(level="DEBUG")
        logger = logging.getLogger(__name__)
    
    test_decode1()
    test_resend()
    test_build_same()
    test_build_modified()
    
    logger.info("all tests passed!")
