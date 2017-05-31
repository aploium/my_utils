#!/usr/bin/env python3
# coding=utf-8

import logging
import logging.handlers
import err_hunter

FORMAT = "[%(levelname)s %(asctime)s %(module)s.%(funcName)s#%(lineno)d] %(message)s"
logging.basicConfig(
    format=FORMAT,
    level=logging.DEBUG,
)

err_hunter.apply_handler("https://api.dyn.li/log", method="POST")

log = logging.getLogger(__name__)

log.info("info")


def func3():
    monkey = 3
    a = 1 / 0


def func2():
    dog = 1
    func3()


def func():
    local_var = 23333
    log.error("hello world", extra={"cat": 1})


try:
    func2()
except:
    func()
