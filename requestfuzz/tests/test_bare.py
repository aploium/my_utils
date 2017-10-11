#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

import cgi
import requests
import err_hunter
import copy

from ..request import FuzzableRequest
from ..bare import BareLoader

logger = err_hunter.getLogger()


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
    request = BareLoader(request_bin, real_host="example.com")
    assert request.method == request.command == "POST"
    # header大小写不敏感
    assert request.headers["accept"] == "undefined"
    assert request.headers["Accept"] == "undefined"
    # 保证cookies的顺序和值和原始一样
    assert tuple(request.cookies.items())[:3] == (
        ('t', 'qwertyuiop'),
        ('_uab_collina', '1501125267079'),
        ('cna', 'zxcvbnm'),
    )

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

    r = BareLoader(request_bin)

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
    r = BareLoader(request_bin, real_host="httpbin.org")

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


def resend(req, pattern=b'<h1>Example Domain</h1>'):
    tor = req.to_requests()
    r = requests.request(**tor)
    assert pattern in r.content
    return r


def build_same(r):
    def _decode(v):
        if isinstance(v, six.binary_type):
            return v.decode("UTF-8")
        else:
            return v

    # --- 测试什么都不变的情况下与原有数据保持相同
    same = BareLoader.build(old=r)

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


def build_modified(r):
    """

    Args:
        r (BareLoader):
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

    new = BareLoader.build(
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


def compare_bareloader_fuzzable(b, f):
    assert isinstance(b, BareLoader)
    assert isinstance(f, FuzzableRequest)

    for name in [
        "query", "method", "host", "port", "path",
        "protocol", "scheme",
        "headers", "cookies",
    ]:
        try:
            assert getattr(b, name) == getattr(f, name)
        except:
            raise
    assert tuple(b.headers.items()) == tuple(f.headers.items())
    assert tuple(b.cookies.items()) == tuple(f.cookies.items())

    _temp = tuple(b.headers.items())
    for k in f.headers.keys():
        assert (k, f.headers[k]) in _temp

    _temp = tuple(b.cookies.items())
    for k in f.cookies.keys():
        assert (k, f.cookies[k]) in _temp

    return f


def test_post():
    r = test_decode_post()
    resend(r)
    build_same(r)

    # modify
    rm = build_modified(r)
    resend(rm)

    compare_bareloader_fuzzable(r, r.to_fuzzable())
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r))
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r.raw))
    compare_bareloader_fuzzable(r, r.to_fuzzable().fork())
    compare_bareloader_fuzzable(rm, rm.to_fuzzable())
    compare_bareloader_fuzzable(rm, FuzzableRequest.from_bare(rm))
    _fz = FuzzableRequest.from_bare(rm.raw)
    _fz.scheme = "https"
    _fz.port = 443
    compare_bareloader_fuzzable(rm, _fz)
    compare_bareloader_fuzzable(rm, rm.to_fuzzable().fork())


def test_get():
    r = test_decode_get()
    resend(r, b"uCX6YrzPpTmax")
    build_same(r)
    build_modified(r)
    compare_bareloader_fuzzable(r, r.to_fuzzable())
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r))
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r.raw))
    compare_bareloader_fuzzable(r, r.to_fuzzable().fork())


def test_multipart():
    r = test_decode_multipart()
    compare_bareloader_fuzzable(r, r.to_fuzzable())
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r))
    compare_bareloader_fuzzable(r, FuzzableRequest.from_bare(r.raw))
    compare_bareloader_fuzzable(r, r.to_fuzzable().fork())
    resend(r, b'"upload": "afasfafasfasfa"')


def test_json():
    request_bin = b'''POST /anything HTTP/1.1
Host: httpbin.org
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:55.0) Gecko/20100101 Firefox/55.0
Accept: */*
Accept-Language: zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3
Accept-Encoding: gzip, deflate, br
Content-Type: application/json
X-Requested-With: XMLHttpRequest
Referer: http://httpbin.org/
Content-Length: 37
Cookie: some=cookie
Connection: close

{"json_content":"helloworld"}'''
    fz = FuzzableRequest.from_bare(request_bin)
    assert not fz.data
    assert fz.json == {"json_content": "helloworld"}
    assert fz.to_requests()["json"] == {"json_content": "helloworld"}

    assert fz.fork().json is not fz.json
