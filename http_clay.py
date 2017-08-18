# coding=utf-8
# --------------- 以下代码用于提供py2/py3兼容 ---------------
from __future__ import absolute_import, division, print_function, unicode_literals
# from future.builtins import *
import future.utils as six
from future import standard_library

try:
    standard_library.install_aliases()
except:
    _future_standard_library_load_success = False
else:
    _future_standard_library_load_success = True
# --------------- END COMPATIBLE LAYER ---------------

from io import BytesIO
import re
import json
import cgi
import copy
from collections import OrderedDict

try:
    from future.backports.http.server import BaseHTTPRequestHandler
except:
    from BaseHTTPServer import BaseHTTPRequestHandler
from future.backports.http.cookies import SimpleCookie
from future.backports.urllib import parse

from bottle import FormsDict, FileUpload

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
    dic = OrderedMultiDict()
    pairs = parse.parse_qsl(qsl)
    for name, value in pairs:
        dic[name] = value
    
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


class OrderedMultiDict(FormsDict):
    def __init__(self, *a, **k):
        self.dict = OrderedDict((k, [v]) for (k, v) in OrderedDict(*a, **k).items())
    
    def items(self):
        return super(OrderedMultiDict, self).allitems()


class BareRequest(BaseHTTPRequestHandler):
    def __init__(self, request_bin, scheme="http", real_host=None, port=None):
        self.rfile = BytesIO(request_bin)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()  # 这里会把header都读取掉
        self.body = self._load_body()  # header之后的内容是body
        
        self._path = self.path
        
        if six.PY2:
            self._path = self._path.decode("UTF-8")
            if not _future_standard_library_load_success:
                for key in tuple(self.headers.keys()):
                    self.headers[key] = self.headers[key].decode("UTF-8")
        
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
            # py2中, SimpleCookie是会丢失顺序的, 所以需要人工进行一次重排
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
        if self.scheme == "https" and self.port == 443 \
                or self.scheme == "http" and self.port == 80:
            return self.real_host
        else:
            return "{}:{}".format(self.real_host, self.port)
    
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
    
    def to_burp(self):
        """
        返回供burp使用的格式
        
        Returns:
            Tuple[List[str], bytes]:
        """
        lines = [self.raw_requestline.decode("UTF-8").rstrip("\r\n")]
        lines.extend(self.headers.as_string().splitlines())
        return lines, self.body


# ----------------------------------------------------------------
# -----------------------  BEGIN TESTS ---------------------------
# ----------------------------------------------------------------

def test_decode1():
    request_bin = b'''POST /some-path.html?fromSite=-2&fromSite=another&appName=cat HTTP/1.1
Host: www.example.com
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0
Accept: undefined
Accept-Language: zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3
Accept-Encoding: gzip, deflate, br
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: http://www.example.com/referer
Content-Length: 87
Cookie: t=qwertyuiop; _uab_collina=1501125267079; cna=zxcvbnm; _umdata=A502B1276E
Connection: close

loginId=abcdef.io&loginId=another-loginId&appName=cat&appEntrance=cat&bizParams=c'''
    request = BareRequest(request_bin, real_host="127.0.0.1")
    assert request.method == request.command == "POST"
    # 保证cookies的顺序和值和原始一样
    assert tuple(request.cookies.items())[:3] == (('t', 'qwertyuiop'),
                                                  # ('t', 'anothert'),
                                                  ('_uab_collina', '1501125267079'),
                                                  ('cna', 'zxcvbnm'),), tuple(request.cookies.items())
    assert request.host == "www.example.com"
    assert request.text[:16] == 'loginId=abcdef.i'
    assert request.is_json is False
    assert request.is_form is True
    # 保证forms, 并且支持相同value多次出现
    assert tuple(request.forms.items())[:4] == (('loginId', 'abcdef.io'),
                                                ('loginId', 'another-loginId'),
                                                ('appName', 'cat'),
                                                ('appEntrance', 'cat'),)
    assert request.POST == request.forms  # 在本例情况下两者相同
    assert request.raw in request_bin
    assert request.content_length == 87
    assert request.user_agent == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:54.0) Gecko/20100101 Firefox/54.0"
    assert request.is_xhr is True
    assert request.query_string == "fromSite=-2&fromSite=another&appName=cat"
    # 保证顺序, 并支持重复
    assert tuple(request.query.items()) == (('fromSite', '-2'),
                                            ('fromSite', 'another'),
                                            ('appName', 'cat'))
    
    return request


def test_resend():
    import requests
    req = test_decode1()
    tor = req.to_requests()
    print(tor)
    r = requests.request(**tor)
    return r


if __name__ == "__main__":
    test_decode1()
    test_resend()
