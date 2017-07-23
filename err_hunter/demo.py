#!/usr/bin/env python3
# coding=utf-8
from __future__ import unicode_literals
import requests
import err_hunter


def error_func():
    monkey = 3
    a = 1 / 0  # this will raise error
    universe = 42  # never reached


def func():
    cat = 7
    r = requests.get("http://example.com")
    error_func()
    monkey = 7


some_global_var = {"a": "b"}
try:
    func()
except:
    err_hunter.print_exc(
        interested=[  # we want to see things inside requests' response
            "requests.models.Response"]
    )
