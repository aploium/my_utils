#!/usr/bin/env python3
# coding=utf-8

import logging
import logging.handlers

from err_hunter import MyHTTPHandler

FORMAT = "[%(levelname)s %(asctime)s %(module)s.%(funcName)s#%(lineno)d] %(message)s"
logging.basicConfig(
    format=FORMAT,
    level=logging.DEBUG,
)
handler = MyHTTPHandler("https://api.dyn.li/log", method="POST")
formatter = logging.Formatter(fmt=FORMAT)
handler.setFormatter(formatter)

handler.setLevel(logging.WARNING)
logging.getLogger().addHandler(handler)

log = logging.getLogger(__name__)

log.info("info")


def func():
    local_var = 23333
    log.error("hello world", extra={"cat": 1})


try:
    a = 1 / 0
except:
    func()
