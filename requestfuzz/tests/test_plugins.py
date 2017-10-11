#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

import requests
from requestfuzz import FuzzableRequest, HTTPHeaders
from requestfuzz.plugin import AutoHeader, AutoCleanParam


def test_auto_header():
    fz = FuzzableRequest(
        "http://httpbin.org/anything",
        headers={"User-Agent": "foobar"},
        plugins=[AutoHeader],
    )

    assert fz.headers == HTTPHeaders([
        ('User-Agent', 'foobar'),
        ('Accept-Encoding', 'gzip, deflate'),
        ('Accept-Language', 'zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2'),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
        ('Referer', 'http://httpbin.org/anything')
    ])

    r = requests.request(**fz.to_requests())
    assert r.json()["headers"] == {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2',
        'Connection': 'close',
        'Host': 'httpbin.org',
        'Referer': 'http://httpbin.org/anything',
        'User-Agent': 'foobar'
    }


def test_auto_clean_param():
    fz = FuzzableRequest(
        "http://httpbin.org/anything?spm=useless&_t=123&a=b&c=d",
        plugins=[AutoCleanParam],
    )
    assert fz.query_string == "a=b&c=d"


def test_two_plugins():
    # AutoClean 在 AutoHeader 之前调用,
    #   所以referer里面 **没有** spm
    fz = FuzzableRequest(
        "http://httpbin.org/anything?spm=useless&_t=123&a=b&c=d",
        headers={"User-Agent": "foobar"},
        plugins=[AutoCleanParam, AutoHeader],
    )

    assert fz.headers == HTTPHeaders([
        ('User-Agent', 'foobar'),
        ('Accept-Encoding', 'gzip, deflate'),
        ('Accept-Language', 'zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2'),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
        ('Referer', 'http://httpbin.org/anything?a=b&c=d')
    ])

    assert fz.query_string == "a=b&c=d"

    # -----------------------
    # AutoClean 在 AutoHeader 之后调用,
    #   所以referer里面没 **有** spm
    fz = FuzzableRequest(
        "http://httpbin.org/anything?spm=useless&_t=123&a=b&c=d",
        headers={"User-Agent": "foobar"},
        plugins=[AutoHeader, AutoCleanParam],
    )

    assert fz.headers == HTTPHeaders([
        ('User-Agent', 'foobar'),
        ('Accept-Encoding', 'gzip, deflate'),
        ('Accept-Language', 'zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2'),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
        ('Referer', 'http://httpbin.org/anything?spm=useless&_t=123&a=b&c=d')
    ])

    assert fz.query_string == "a=b&c=d"
