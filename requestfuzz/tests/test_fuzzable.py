#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

if six.PY3:
    import collections
else:
    from future.moves import collections

import requests

from requestfuzz.request import FuzzableRequest
from requestfuzz.datastructure import HTTPHeaders, QueryDict, Cookie
from requestfuzz import utils
import err_hunter

logger = err_hunter.getLogger()


def make_simple_req():
    return FuzzableRequest("http://httpbin.org/anything?a=1&b=2&c=3&a=x&a=y")


def make_complex_req():
    return FuzzableRequest(
        "http://www.httpbin.org/anything?a=1&b=2&c=3&a=x&a=y",
        method="POST",
        data="a=b&c=d&c=e&e=x&x=f",  # 允许传入字符串/dict/kv-pairs
        headers=collections.OrderedDict([
            # 允许传入dict/kv-pairs, 不过只有 OrderedDict 会保留顺序
            ("User-Agent", "RequestFuzz"),
            ("referer", "http://example.com"),
            ("conneCtion", "close"),  # 允许异形headers
            ("Accept", "*/*"),
        ]),
        cookies=[  # 允许传入 字符串/dict/kv-pairs
            ("Answer", "42"), ("Sess", "x"), ("sky", "net")],
    )


def test_basic():
    fz = make_simple_req()
    assert fz.port == 80
    assert fz.host == fz.netloc == "httpbin.org"
    assert fz.protocol == "HTTP/1.1"
    assert tuple(fz.query.items()) == (('a', '1'), ('b', '2'), ('c', '3'), ('a', 'x'), ('a', 'y'))
    assert fz.query_string == "a=1&b=2&c=3&a=x&a=y"
    assert fz.scheme == "http"
    assert fz.url == "http://httpbin.org/anything?a=1&b=2&c=3&a=x&a=y"
    assert fz.url.without_path == "http://httpbin.org"
    assert fz.url.without_query == "http://httpbin.org/anything"
    assert not fz.headers
    assert not fz.cookies
    assert not fz.data
    assert not fz.json

    fz.query["e"] = "233"
    assert tuple(fz.query.items()) == (('a', '1'), ('b', '2'), ('c', '3'), ('a', 'x'), ('a', 'y'), ("e", "233"))
    assert fz.query_string == 'a=1&b=2&c=3&a=x&a=y&e=233'
    assert fz.url == 'http://httpbin.org/anything?a=1&b=2&c=3&a=x&a=y&e=233'

    fz.query["a"] = "0day"
    assert tuple(fz.query.items()) == (('a', '0day'), ('b', '2'), ('c', '3'), ("e", "233"))
    assert fz.query_string == 'a=0day&b=2&c=3&e=233'
    assert fz.url == 'http://httpbin.org/anything?a=0day&b=2&c=3&e=233'

    del fz.query["a"]
    assert fz.query_string == 'b=2&c=3&e=233'
    assert tuple(fz.query.items()) == (('b', '2'), ('c', '3'), ("e", "233"))

    fz.query["c"] = "4"
    assert fz.query_string == 'b=2&c=4&e=233'

    fz.query.add("c", "5")
    assert fz.query_string == 'b=2&c=4&e=233&c=5'

    fz.query.update({"d": "7"})
    assert fz.query_string == 'b=2&c=4&e=233&c=5&d=7'

    assert "d" in fz.query


def test_headers():
    fz = make_simple_req()

    # ------ headers ---------
    assert fz.headers is fz.headers  # 即不是每次调用生成新的
    assert isinstance(fz.headers, HTTPHeaders)
    assert utils.like_dict(fz.headers)

    fz.headers["X-ReqFuzz"] = "0day"
    assert fz.headers["x-reqfuzz"] == fz.headers["X-ReqFuzz"] == "0day"
    assert "x-reqfuzz" in fz.headers
    assert "X-ReqFuzz" in fz.headers

    fz.headers["x-H1"] = "skynet"
    fz.headers["X-h2"] = "skynet2"
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('x-H1', 'skynet'), ('X-h2', 'skynet2'))

    fz.headers["X-h1"] = "skynet1"
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('x-H1', 'skynet1'), ('X-h2', 'skynet2'))

    fz.headers.update({"x-h1": "sky", "x-h3": "net"})
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('x-H1', 'sky'), ('X-h2', 'skynet2'), ('x-h3', 'net'))

    del fz.headers["X-h1"]
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('X-h2', 'skynet2'), ('x-h3', 'net'))

    fz.headers.add("X-H2", "another")
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('X-h2', 'skynet2'),
                                         ('x-h3', 'net'),
                                         ('X-h2', 'another'))
    fz.headers["x-h2"] = "h2"
    assert tuple(fz.headers.items()) == (('X-ReqFuzz', '0day'), ('X-h2', 'h2'), ('x-h3', 'net'))

    assert dict(fz.headers) == {'X-ReqFuzz': '0day', 'X-h2': 'h2', 'x-h3': 'net'}


def test_seturl():
    fz = make_simple_req()
    fz.url = "https://example.com:4443/index.html?a=2&b=2"
    assert fz.url == "https://example.com:4443/index.html?a=2&b=2"
    assert fz.path == "/index.html"
    assert fz.netloc == 'example.com:4443'
    assert fz.port == 4443
    assert fz.scheme == "https"
    assert fz.query_string == 'a=2&b=2'
    assert fz.host == "example.com"


def test_to_requests():
    fz = make_complex_req()

    assert fz.url == 'http://www.httpbin.org/anything?a=1&b=2&c=3&a=x&a=y'

    assert tuple(fz.headers.items()) == (('User-Agent', 'RequestFuzz'),
                                         ('referer', 'http://example.com'),
                                         ('conneCtion', 'close'),
                                         ('Accept', '*/*'))
    assert fz.headers["connection"] == fz.headers["conneCtion"]
    assert fz.headers["reFerer"] == fz.headers["referer"]

    assert tuple(fz.cookies.items()) == (('Answer', '42'), ('Sess', 'x'), ('sky', 'net'))
    assert tuple(fz.data.items()) == (('a', 'b'), ('c', 'd'), ('c', 'e'), ('e', 'x'), ('x', 'f'))
    assert fz.method == "POST"

    assert fz.to_requests() == {
        'data': QueryDict([('a', 'b'), ('c', 'd'), ('c', 'e'), ('e', 'x'), ('x', 'f')]),
        'headers': HTTPHeaders(
            [('User-Agent', 'RequestFuzz'), ('referer', 'http://example.com'),
             ('conneCtion', 'close'), ('Accept', '*/*'),
             # ('Cookie', 'Answer=42; Sess=x; sky=net')
             ]),
        'method': 'POST',
        'params': QueryDict([('a', '1'), ('b', '2'), ('c', '3'), ('a', 'x'), ('a', 'y')]),
        'url': 'http://www.httpbin.org/anything',
        "cookies": Cookie('Answer=42; Sess=x; sky=net'),
        "json": None,
        "files": None,
    }

    _req = fz.to_requests()
    assert _req["params"] is not fz.query
    assert _req["data"] is not fz.data
    assert _req["headers"] is not fz.headers

    # _req["proxies"] = {"http":"http://127.0.0.1:8080"}

    r = requests.request(**_req)

    rj = r.json()
    assert rj["args"] == {'a': 'y', 'b': '2', 'c': '3'}
    assert rj["data"] == ""
    assert rj["form"] == {'a': 'b', 'c': ['d', 'e'], 'e': 'x', 'x': 'f'}

    # 因为对cookies构建还有问题, 所以在 py3.6 以下版本中,
    #   cookies的顺序不会被保留, 这里跳过对 cookies 的顺序的test
    #   而只是检测 cookies 的存在性
    assert "Answer=42" in rj["headers"]["Cookie"]
    assert "Sess=x" in rj["headers"]["Cookie"]
    assert "sky=net" in rj["headers"]["Cookie"]
    del rj["headers"]["Cookie"]

    assert rj["headers"] == {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'close',
        'Content-Length': '19',
        'Content-Type': 'application/x-www-form-urlencoded',
        # 'Cookie': 'Answer=42; Sess=x; sky=net',
        'Host': 'www.httpbin.org',
        'Referer': 'http://example.com',
        'User-Agent': 'RequestFuzz'
    }
    assert rj["method"] == "POST"
    assert rj["url"] == 'http://www.httpbin.org/anything?a=y&b=2&c=3'


def test_to_bare(fz=None):
    fz = fz or make_complex_req()

    assert fz.to_bare() == \
           b"""\
POST /anything?a=1&b=2&c=3&a=x&a=y HTTP/1.1\r\n\
User-Agent: RequestFuzz\r\n\
referer: http://example.com\r\n\
conneCtion: close\r\n\
Accept: */*\r\n\
Cookie: Answer=42; Sess=x; sky=net\r\n\
Content-Length: 19\r\n\
Content-Type: application/x-www-form-urlencoded\r\n\
Host: www.httpbin.org\r\n\
\r\n\
a=b&c=d&c=e&e=x&x=f"""


def test_fork_complex():
    fz = make_complex_req()

    # 什么都不变, 应该是完全相同的
    fk = fz.fork()
    assert fz.to_bare() == fk.to_bare()

    assert fk.query is not fz.query
    assert fk.data is not fz.data
    assert fk.headers is not fz.headers
    assert fk.cookies is not fz.cookies

    fk = fz.fork(
        method="PUT", path="/put",
        query=[("foo", "bar"), ("c", "changed")],  # 以merge形式合并
        data=[("bar", "cat"), ("a", "chg")],
        headers=[("User-Agent", "AnotherUA"), ("X-method", "PUT")],
        cookies=[('Answer', '43'), ("cook", "ie")],
    )

    assert fk.method == "PUT"
    assert fk.path == "/put"
    assert tuple(fk.query.items()) == (('a', '1'), ('b', '2'), ('c', 'changed'),
                                       ('a', 'x'), ('a', 'y'), ('foo', 'bar'))
    assert fk.query_string == 'a=1&b=2&c=changed&a=x&a=y&foo=bar'
    assert fk.url == 'http://www.httpbin.org/put?a=1&b=2&c=changed&a=x&a=y&foo=bar'
    assert tuple(fk.data.items()) == (('a', 'chg'), ('c', 'd'), ('c', 'e'),
                                      ('e', 'x'), ('x', 'f'), ('bar', 'cat'))
    assert tuple(fk.headers.items()) == (('User-Agent', 'AnotherUA'),
                                         ('referer', 'http://example.com'),
                                         ('conneCtion', 'close'),
                                         ('Accept', '*/*'),
                                         ('X-method', 'PUT'))
    assert tuple(fk.cookies.items()) == (('Answer', '43'), ('Sess', 'x'),
                                         ('sky', 'net'), ('cook', 'ie'))

    assert fk.to_bare() == b"""\
PUT /put?a=1&b=2&c=changed&a=x&a=y&foo=bar HTTP/1.1\r\n\
User-Agent: AnotherUA\r\n\
referer: http://example.com\r\n\
conneCtion: close\r\n\
Accept: */*\r\n\
X-method: PUT\r\n\
Cookie: Answer=43; Sess=x; sky=net; cook=ie\r\n\
Content-Length: 29\r\n\
Content-Type: application/x-www-form-urlencoded\r\n\
Host: www.httpbin.org\r\n\
\r\n\
a=chg&c=d&c=e&e=x&x=f&bar=cat"""

    test_to_bare(fz)  # fork之前的不应该发生改变


def test_strange_cookie():
    fz = make_simple_req()
    fz.cookies["strange"] = "\"\'\\\x9f ;"
    assert str(fz.cookies) == r'''strange="\"'\\\237 \073"'''


def test_to_jsonable():
    import json
    fz = make_complex_req()
    jsonable = fz.to_jsonable()
    assert json.loads(json.dumps(jsonable)) == jsonable


def test_multipart():
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
    fz = FuzzableRequest.from_bare(request_bin)

    assert fz.data == QueryDict({"caption": "aaaaa"})
    assert fz.data["caption"] == "aaaaa"

    f = fz.files["upload"]
    import cgi
    assert isinstance(f, cgi.FieldStorage)
    assert fz.files["upload"].file.getvalue() == b'afasfafasfasfa'
    assert fz.files["upload"] is f
    assert f.file.getvalue() == b'afasfafasfasfa'
    assert f.outerboundary == b"----WebKitFormBoundaryEW35oPYWK6qwibcP"
    assert f.disposition == "form-data"
    assert f.name == "upload"
    assert f.filename == "abc.txt"
    assert f.type == "text/plain"
