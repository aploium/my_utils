#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

import collections
import json

from future.backports.urllib import parse
from requestfuzz import FuzzableRequest
from requestfuzz.payload import Payload
from requestfuzz.mutant import MutantBase, ShallowMutant, PayloadFactoryBase, DeepMutant, HeadersMutant
from requestfuzz.tests.test_fuzzable import make_complex_req


class DummyPayloadFactory(PayloadFactoryBase):
    def make(self, key=None, value=None, place=None, node=None):
        yield Payload("{}__{}".format(key, value)), {}


def test_payload_factory_dummy():
    fz = make_complex_req()
    pf = DummyPayloadFactory(fz)
    
    assert list(pf.make(key="cat", value="dog")) \
           == [(Payload("cat__dog"), {})]


def test_shallow_mutant():
    fz = make_complex_req()
    mutant = ShallowMutant(DummyPayloadFactory)
    
    expected = [
        # query
        b"/anything?a=a__1&b=2&c=3",
        b"/anything?a=1&b=b__2&c=3&a=x&a=y",
        b"/anything?a=1&b=2&c=c__3&a=x&a=y",
        b"/anything?a=a__x&b=2&c=3",
        b"/anything?a=a__y&b=2&c=3",
        
        # data
        b"a=a__b&c=d&c=e&e=x&x=f",
        b"a=b&c=c__d&e=x&x=f",
        b"a=b&c=c__e&e=x&x=f",
        b"a=b&c=d&c=e&e=e__x&x=f",
        b"a=b&c=d&c=e&e=x&x=x__f",
    ]
    
    for atk_fz, correct in zip(mutant.make(fz), expected):
        assert correct in atk_fz.to_bare()


def test_deep_mutant_simple():
    """在传入值不涉及递归的情况下, 行为应该和shallow是 *几乎* 相同的
    除了一个优点以外: 不会丢失重复key
    """
    fz = make_complex_req()
    mutant = DeepMutant(DummyPayloadFactory)
    
    expected = [
        # query
        b"/anything?a=a__1&b=2&c=3&a=x&a=y",
        b"/anything?a=1&b=b__2&c=3&a=x&a=y",
        b"/anything?a=1&b=2&c=c__3&a=x&a=y",
        b"/anything?a=1&b=2&c=3&a=a__x&a=y",
        b"/anything?a=1&b=2&c=3&a=x&a=a__y",
        
        # data
        b"a=a__b&c=d&c=e&e=x&x=f",
        b"a=b&c=c__d&c=e&e=x&x=f",
        b"a=b&c=d&c=c__e&e=x&x=f",
        b"a=b&c=d&c=e&e=e__x&x=f",
        b"a=b&c=d&c=e&e=x&x=x__f",
    ]
    
    for atk_fz, correct in zip(mutant.make(fz), expected):
        assert correct in atk_fz.to_bare()


def test_deep_mutant_simple2():
    """fz的data是json, 其他不变"""
    fz = make_complex_req()
    fz.bin_body = json.dumps(collections.OrderedDict([
        ("x", "1"),
        ("b", "2"),
        ("z", "3"),
        ("kerbin", "kerbal"),
    ])).encode("UTF-8")
    
    mutant = DeepMutant(DummyPayloadFactory)
    
    expected = [
        # query
        b"/anything?a=a__1&b=2&c=3&a=x&a=y",
        b"/anything?a=1&b=b__2&c=3&a=x&a=y",
        b"/anything?a=1&b=2&c=c__3&a=x&a=y",
        b"/anything?a=1&b=2&c=3&a=a__x&a=y",
        b"/anything?a=1&b=2&c=3&a=x&a=a__y",
        
        # data
        b"""{"x": "x__1", "b": "2", "z": "3", "kerbin": "kerbal"}""",
        b"""{"x": "1", "b": "b__2", "z": "3", "kerbin": "kerbal"}""",
        b"""{"x": "1", "b": "2", "z": "z__3", "kerbin": "kerbal"}""",
        b"""{"x": "1", "b": "2", "z": "3", "kerbin": "kerbin__kerbal"}""",
    ]
    
    for atk_fz, correct in zip(mutant.make(fz), expected):
        assert correct in atk_fz.to_bare()


def test_deep_mutant_complex():
    """测试复杂的包含递归的项"""
    fz = make_complex_req()
    fz.query["c"] = json.dumps(dict(
        j="son",
        f="yet=another&form=1",
    ))
    fz.data["e"] = parse.urlencode([
        ("cat", "dog"),
        ("j2", '{"foo":"bar"}'),
    ])
    mutant = DeepMutant(DummyPayloadFactory)
    
    expected = [
        # query
        b"/anything?a=a__1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=b__2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=2&c=c__%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=a__x&a=y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=x&a=a__y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22j__son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22f__yet%3Danother%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Dyet__another%26form%3D1%22%7D&a=x&a=y",
        b"/anything?a=1&b=2&c=%7B%22j%22%3A+%22son%22%2C+%22f%22%3A+%22yet%3Danother%26form%3Dform__1%22%7D&a=x&a=y",
        
        # data
        b"a=a__b&c=d&c=e&e=cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2522bar%2522%257D&x=f",
        b"a=b&c=c__d&c=e&e=cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2522bar%2522%257D&x=f",
        b"a=b&c=d&c=c__e&e=cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2522bar%2522%257D&x=f",
        b"a=b&c=d&c=e&e=e__cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2522bar%2522%257D&x=f",
        b"a=b&c=d&c=e&e=cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2522bar%2522%257D&x=x__f",
        b"a=b&c=d&c=e&e=cat%3Dcat__dog%26j2%3D%257B%2522foo%2522%253A%2B%2522bar%2522%257D&x=f",
        b"a=b&c=d&c=e&e=cat%3Ddog%26j2%3Dj2__%257B%2522foo%2522%253A%2B%2522bar%2522%257D&x=f",
        b"a=b&c=d&c=e&e=cat%3Ddog%26j2%3D%257B%2522foo%2522%253A%2B%2522foo__bar%2522%257D&x=f",
    ]
    
    for atk_fz, correct in zip(mutant.make(fz), expected):
        assert correct in atk_fz.to_bare()
        # print(atk_fz.to_bare().decode())


def test_headers_mutant():
    fz = make_complex_req()
    fz.headers["User-Agent"] = "monkey"
    fz.headers["Referer"] = "http://cat.com"
    mutant = HeadersMutant(DummyPayloadFactory)
    expected = [
        b"User-Agent: User-agent__monkey",
        b"X-Forward-For: X-Forward-For__",
        b"referer: Referer__http://cat.com",
    ]
    
    for atk_fz, correct in zip(mutant.make(fz), expected):
        assert correct in atk_fz.to_bare()


if __name__ == '__main__':
    test_deep_mutant_simple()
    test_deep_mutant_simple2()
    test_deep_mutant_complex()
    test_headers_mutant()
