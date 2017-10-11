#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

from urllib import parse

from requestfuzz import Url


def test_url_basic():
    url = Url("http://example.com:8080/foo/bar.php?q=cat&q=dog#frag")

    assert url == str(url) == url.url == "http://example.com:8080/foo/bar.php?q=cat&q=dog#frag"
    assert url.all_but_scheme == 'example.com:8080/foo/bar.php?q=cat&q=dog#frag'
    assert url.ext == ".php"
    assert url.filename == 'bar.php'
    assert url.fragment == 'frag'
    assert url.host == "example.com"
    assert url.netloc == "example.com:8080"
    assert url.path == '/foo/bar.php'
    assert url.path_qs == '/foo/bar.php?q=cat&q=dog'
    assert url.port == 8080
    assert tuple(url.query.items()) == (('q', 'cat'), ('q', 'dog'))
    assert url.query_string == 'q=cat&q=dog'
    assert url.scheme == "http"
    assert url.without_path == 'http://example.com:8080'
    assert url.without_query == 'http://example.com:8080/foo/bar.php'
    assert url.root_domain == 'example.com'


def test_url_no_scheme():
    url = Url("//example.com")
    assert url.tostr() == str(url) == '//example.com'
    assert url.scheme == ""
    assert url.host == "example.com"
    assert url.port is None

    url = Url("//example.com/x")
    assert url.tostr() == '//example.com/x'
    assert url.scheme == ""
    assert url.host == "example.com"
    assert url.path == "/x"
    assert url.port is None

    url = Url("//example.com:233/x")
    assert url.tostr() == '//example.com:233/x'
    assert url.scheme == ""
    assert url.host == "example.com"
    assert url.path == "/x"
    assert url.port == 233


def test_not_url():
    url = Url("some_path")
    assert url.tostr() == "some_path"
    assert url.host is None
    assert url.scheme == ""
    assert url.host is None
    assert url.port is None
