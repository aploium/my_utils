#!/usr/bin/env python3
# coding=utf-8
import requests
import err_hunter


#
# FORMAT = "[%(levelname)s %(asctime)s %(module)s.%(funcName)s#%(lineno)d] %(message)s"
# logging.basicConfig(
#     format=FORMAT,
#     level=logging.DEBUG,
# )
#
# log = logging.getLogger(__name__)
#
# log.info("info")


def error_func():
    monkey = 3
    a = 1 / 0
    universe = 42


def func():
    cat = 7
    r = requests.get("http://example.com")
    error_func()
    monkey = 7


some_global_var = {"a": "b"}
try:
    func()
except:
    err_hunter.print_exc()
