#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

import pytest

from requestfuzz import FuzzableRequest


def _fmt_line_sep(bare, line_sep=b"\r\n"):
    return line_sep.join(bare.splitlines(False))


def test_rebuild_bare1():
    bare = b"""GET / HTTP/1.1
Host: 11.22.33.44
User-Agent: HTTPie/0.9.9
Accept-Encoding: identity
Accept: */*
Connection: keep-alive


"""
    bare = _fmt_line_sep(bare)
    assert FuzzableRequest.from_bare(bare).to_bare() == bare


def test_rebuild_bare2():
    bare = b"""GET / HTTP/1.1
Host: www.baidu.com
Connection: keep-alive
Cache-Control: max-age=0
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Accept-Encoding: identity
Accept-Language: zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2,cy;q=0.2
Cookie: __cfduid=aa; BAIDUID="bb:FG=1"; PSTM=cc; BIDUPSID=dd; MCITY=-%3A; ispeed_lsm=2; BD_HOME=0; BD_UPN=123253; BD_CK_SAM=1; PSINO=5; H_PS_PSSID=as12rf; BDORZ=FEEFerg; BDSVRTM=0


"""
    bare = _fmt_line_sep(bare)
    assert FuzzableRequest.from_bare(bare).to_bare() == bare


def test_rebuild_bare4():
    bare = b"""\
POST /vulnerabilities/exec/ HTTP/1.1
Host: some.domain.com:2333
Connection: keep-alive
Content-Length: 26
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.2333.113 Safari/537.36
Content-Type: application/x-www-form-urlencoded
Accept: */*
Accept-Encoding: gzip, deflate
Accept-Language: zh-CN,zh;q=0.8
Cookie: PHPSESSID=vvvvvvvvvvvv; security=low

ip=127.0.0.1&Submit=Submit"""
    bare = _fmt_line_sep(bare)
    assert FuzzableRequest.from_bare(bare).to_bare() == bare
