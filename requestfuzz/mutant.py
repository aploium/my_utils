#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future import utils as six

from .datastructure import OrderedMultiDict
from .recursive_parse import *
from .utils import ensure_unicode

try:  # for type hint
    from typing import Type
    from .request import FuzzableRequest
    from .payload import Payload
except:
    pass


class PayloadFactoryBase(object):  # TODO: 有待改进
    """
    用于产生填入各个可修改位点的payload
    在初始化时给出fz, .make() 对特定位点产生payload

    Args:
        ori_fz(FuzzableRequest): 原始fz
    """

    def __init__(self, ori_fz):
        self.ori_fz = ori_fz

    def make(self, key=None, value=None, place=None, node=None):
        """
        给定一个待修改的位置, 生成此位点可用的payload

        Args:
            key (str): 待修改位置的原始key
            value (str): 待修改位置的原始value
            place (str): 位置名
            node (BaseNode): 解析树中的对应节点, 传入的是原始树的副本

        Yields:
            tuple[Payload, dict]:
                返回此位置可能的一系列新值, 每一项为 tuple[Payload, meta]
        """
        raise NotImplementedError


class MutantBase(object):
    """
    用于生成fz的变体

    Args:
        place(str): 标记此factory会修改request上的哪一部分
                    例如: query headers
        factory_class(Type[PayloadFactoryBase]):
                    用于对每个可以修改的地方产生一系列的变体
                    给定修改点, 给出此处可以应用的一系列payload
    """
    EXCLUDES = dict(
        # partmatch对大小写不敏感
        partmatch=("csrf", "spm", "__preventcache", "timestamp", "sectoken", "sec_token"),
        fullmatch=("_", "_t", "callback")
    )

    def __init__(self, factory_class=None, excludes=EXCLUDES):
        self.factory_class = factory_class
        self.excludes = excludes

    def make(self, fz):
        """
        根据fz生成变体
        Args:
            fz (FuzzableRequest):

        Yields:
            FuzzableRequest: 返回一系列fz, 都是对原fz的副本
        """
        raise NotImplementedError

    def should_skip(self, key=None, value=None):
        """
        判断一组潜在位点是否应该跳过
        """
        if isinstance(key, six.string_types):
            key_lower = key.lower()
            if any((exc in key_lower) for exc in self.excludes['partmatch']):
                return True

        if key in self.excludes['fullmatch']:
            return True

        return False


class ShallowMutant(MutantBase):
    """
    遍历query和data, 并分别将其中每一个value进行修改
    不进行递归遍历

    在返回的 fz.meta 中存储有用于报告的信息

    Warnings:
        由于QueryDict还不完善, 对存在多个相同key的污染有问题,
          复数的key会被丢弃, 只留下一个, 但是他们的value都会被依次遍历到
          eg: a=b&a=c&x=1 -->  a=<payload>b  and  a=<payload>c&x=1
    """
    PLACES = ["query", "data"]

    def make(self, fz):
        """

        Args:
            fz (FuzzableRequest):
        """
        factory = self.factory_class(fz)  # type: PayloadFactoryBase

        for place in self.PLACES:
            dic = getattr(fz, place)  # type: OrderedMultiDict
            for key, value in dic.items():

                if self.should_skip(key, value):
                    continue

                payload_iter = factory.make(key, value=value, place=place)

                for payload, meta in payload_iter:
                    # 在meta中记录的用于debug或用于报告的信息
                    meta.update(payload=payload, key=key, value=value, place=place)
                    kw = {"meta": meta, place: {key: payload.content}}
                    yield fz.fork(**kw)


class DeepMutant(MutantBase):
    PLACES = ["query", "data"]

    def make(self, fz):
        """

        Args:
            fz (FuzzableRequest):
        """

        factory = self.factory_class(fz)

        for place in self.PLACES:
            # 取得data, 这里现在写得有点丑
            if place == "data":
                try:
                    data = ensure_unicode(fz.bin_body)
                except:
                    continue
            elif place == "query":
                data = fz.query_string
            else:
                data = getattr(fz, place)

            root = load(data)

            for node in root.iter_tree():
                if self.should_skip(node.key, node.data):
                    continue

                payload_iter = factory.make(
                    node.key, node.text, place=place, node=node)

                for payload, meta in payload_iter:
                    meta.update(payload=payload, key=node.key, value=node.text, place=place, node=node)
                    new_root = node.fork_tree(payload.content)

                    # 回写
                    new_fz = fz.fork(meta=meta)
                    if place == "data":
                        new_fz.bin_body = new_root.text.encode("UTF-8")
                    else:
                        setattr(new_fz, place, new_root.data)
                    yield new_fz


class HeadersMutant(MutantBase):
    KEYS = ("User-agent", "X-Forward-For", "Referer")

    def make(self, fz):
        """

        Args:
            fz (FuzzableRequest):
        """
        payload_factory = self.factory_class(fz)  # type: PayloadFactoryBase

        for key in self.KEYS:

            value = fz.headers.get(key, "")
            for payload, meta in payload_factory.make(
                    key, value=value, place="headers"):

                # 因为headers中不允许出现\r\n, 出现就会报错, 所以跳过
                #   如果需要污染headers, 请直接指定, 不要在这里用crlf注入
                if "\r" in payload.content or "\n" in payload.content:
                    continue

                meta.update(payload=payload, key=key, value=value)

                new = fz.fork(headers={key: payload.content},
                              meta=meta)
                yield new


class PathMutant(MutantBase):
    def make(self, fz):
        """

        Args:
            fz (FuzzableRequest):
        """
        payload_factory = self.factory_class(fz)  # type: PayloadFactoryBase

        for payload, meta in payload_factory.make(
                "<path>", value=fz.path, place="path"):
            meta.update(payload=payload, value=fz.path)
            new = fz.fork(path=payload.content, meta=meta)
            yield new
