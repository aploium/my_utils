#!/usr/bin/env python3
# coding=utf-8
"""CSRF工具箱"""
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

import weakref
import re
import requests
import logging

from requests.exceptions import RequestException

from .datastructure import OrderedMultiDict
from .plugin import FzPluginBase

try:
    from . import request
except:
    pass
logger = logging.getLogger(__name__)


class UnableGetCSRFTokenError(Exception):
    pass


class BaseCSRF(FzPluginBase):
    """

    Args:
        fz (request.FuzzableRequest): 关联的请求
        token_places (list[tuple[str,str]]):
            请求中包含token的地方, 例如 [("data", "csrf"), ("headers", "token")]
    """
    TOKEN_KEYWORDS = ["csrf", ]
    POTENTIAL_PLACES = ["query", "data", "headers", "json"]

    def __init__(self, fz):
        """

        Args:
            fz (request.FuzzableRequest):
        """
        super(BaseCSRF, self).__init__(fz)
        self.token_places = self.find_token_places()
        self.new_token = None

    def on_init_complete(self):
        self.apply()

    def get_new_token(self):  # TODO:
        """
        获取一个可用token

        请在子类中覆盖掉本方法
        """
        raise NotImplementedError

    @property
    def need_token(self):
        return bool(self.token_places)

    def find_token_places(self):
        """
        检查原始记录中是否 *需要* csrf_token

        即检查有没有特征字段
        """
        token_places = set()

        for place in self.POTENTIAL_PLACES:
            dic = getattr(self.fz, place)  # type: OrderedMultiDict

            if not dic:
                continue

            for key in dic.keys():
                for keyword in self.TOKEN_KEYWORDS:
                    if keyword in key.lower():
                        # 发现一个token
                        token_places.add((place, key))

        return token_places

    def prepare(self, force=False):
        """调用 get_new_token() 来获取token"""
        if self.new_token and not force:
            return
        try:
            self.new_token = self.get_new_token()
        except (UnableGetCSRFTokenError, RequestException) as e:
            logger.warning("unable to get csrf token for %s %s", self.fz
                           .url, e)
            self.new_token = ""

    def write_token(self):
        """将token写入原请求"""
        for (place, csrf_key) in self.token_places:
            # 下面这句话基本等效于, 不过更方便遍历:
            #   self.fz.query[key] = token
            getattr(self.fz, place)[csrf_key] = self.new_token

    def apply(self):
        """将CSRF应用到request里"""
        if not self.need_token:
            # 不需要token, 直接退出
            return

        self.prepare()
        self.write_token()

    def search_csrf_token(self, content):
        # 首先找input
        for (csrf_position, csrf_key) in self.token_places:
            _regex = re.compile(
                r'(?i)<[^>]*name=[\"\']{1,1}%s[\"\']{1,1}[^>]*value\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}' % csrf_key)
            token = _regex.findall(content)
            if token:
                return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*name=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}[^>]*value\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*id=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}[^>]*value\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*name=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}[^>]*content\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*value\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}[^>]*name=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*value\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}[^>]*id=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)<[^>]*content\s*=\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}[^>]*name=[\"\']{1,1}[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        # 其次找带csrf的JavaScript参数值
        _regex = re.compile(
            r'(?i)[a-zA-Z0-9\-\_\.]*csrf[a-zA-Z0-9\-\_\.]*[\'\"]{0,1}\s*[\=\:\,]{1,1}\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)[a-zA-Z0-9\-\_\.]*sec[a-zA-Z0-9\-\_\.]*token[a-zA-Z0-9\-\_\.]*[\'\"]{0,1}\s*[\=\:\,]{1,1}\s*[\"\']{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        _regex = re.compile(
            r'(?i)[a-zA-Z0-9\-\_]*token[a-zA-Z0-9\-\_]*[\'\"]{0,1}\s*[\=\:]{1,1}\s*[\"\'\,]{1,1}([a-zA-Z0-9\-\_]+)[\"\']{1,1}')
        token = _regex.findall(content)
        if token:
            return token[0]

        return ""


class GenericCSRF(BaseCSRF):
    def get_new_token(self):
        """
        获取一个可用token

        请在子类中覆盖掉本方法
        """
        headers = {
            'accept-encoding': "gzip, deflate",
            'accept-language': "zh-CN,zh;q=0.8,en;q=0.6,it;q=0.4,es;q=0.2",
            'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
            'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

        csrf_token = ""
        if 'referer' in self.fz.headers:
            resp = requests.get(self.fz.headers['referer'], headers=headers, cookies=self.fz.cookies, timeout=5)
            csrf_token = self.search_csrf_token(resp.text)

        if csrf_token == "":
            resp = requests.get(self.fz.url.without_path, headers=headers, cookies=self.fz.cookies, timeout=5)
            csrf_token = self.search_csrf_token(resp.text)

        if csrf_token == "":
            resp = requests.get(self.fz.url.without_query, headers=headers, cookies=self.fz.cookies, timeout=5)
            csrf_token = self.search_csrf_token(resp.text)

        if csrf_token == "":
            logger.error("CSRF not found, url=%s" % self.fz.url)

        return csrf_token
