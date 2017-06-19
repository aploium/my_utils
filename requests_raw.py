#!/usr/bin/env python3
# coding=utf-8
r"""
用于获取最原始的http响应原文,
  即直接socket中读出的原始响应头、未解开 gzip/chunk 的响应体
  工作在SSL的上层, SSL对其透明

工作原理:
  hook 掉 requests 的底层 http.client 中的 socket,
  每次读取 socket 中数据的时候, 都会额外复制一份出来

  由于http.client本身会 *丢弃* 原始数据, 所以只能自己把它存下来

  理论上除了额外的内存占用和少许的性能损耗外不会有副作用, 也不会有兼容性风险

使用方法:
  首先 monkey_patch() 打 patch
    这个 patch 可以在任何时候打, 不像 gevent 一样必须在一开始打,
    会影响所有在 patch 之后的 requests 请求
  然后像正常一样使用 requests 发起请求, 得到 response
  使用 get_raw(response) 获取响应原文

限制:
  python3.4+

@零日 <chenze.zcz@alibaba-inc.com>

>>> # BEGIN doctest
>>> monkey_patch()
>>> import requests
>>> import gzip
>>>
>>> # get raw gzipped body
>>> r = requests.get("http://example.com")
>>> raw = get_raw(r)
>>> assert isinstance(raw, bytearray)
>>> assert raw.startswith(b"HTTP/1.1 200 OK\r\n")
>>> dec = gzip.decompress(get_body(raw))
>>> assert dec == r.content
>>> assert "<title>Example Domain</title>" in dec.decode("utf-8")
>>> print("source_ip:{} dest_ip:{}".format(*get_ip(r))) # doctest: +ELLIPSIS
source_ip:(..., ...) dest_ip:(..., 80)
>>>
>>> # chunked encoding
>>> r2 = requests.get("https://www.baidu.com")
>>> raw2 = get_raw(r2)
>>> raw2 # doctest: +ELLIPSIS
bytearray(b'HTTP/1.1 200 OK\r\n...)
>>> assert raw2.startswith(b"HTTP/1.1 200 OK\r\n")
>>> assert b"Transfer-Encoding: chunked" in raw2
>>> dec2 = gzip.decompress(decode_chunked(raw2))
>>> assert dec2 == r2.content
>>> assert b"www.baidu.com" in dec2
>>>
>>> # this url will be 302 redirected to http://example.com/
>>> r3 = requests.get("https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.com%2F")
>>> raw3 = get_raw(r3)
>>> # notice! the intermediate 302 raw content would NOT be record
>>> assert raw3.startswith(b"HTTP/1.1 200 OK\r\n")
>>> # if you want to record the intermediate result, please use `allow_redirects=False`
>>> r4 = requests.get("https://httpbin.org/redirect-to?url=http%3A%2F%2Fexample.com%2F", allow_redirects=False)
>>> raw4 = get_raw(r4)
>>> assert raw4.startswith(b"HTTP/1.1 302 FOUND\r\n")
"""
__all__ = ("monkey_patch", "get_raw", "get_body", "decode_chunked", "get_ip")

import logging
import functools
import http.client
import io

logger = logging.getLogger(__name__)

_already_patched = False


class HookedBufferedReader(io.BufferedReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dumped = bytearray()

    def flush(self, *args, **kwargs):
        result = super().flush(*args, **kwargs)
        if result:
            self.dumped += result
        return result

    def readline(self, *args, **kwargs):
        result = super().readline(*args, **kwargs)
        self.dumped += result
        return result

    def readinto(self, buffer):
        _b = memoryview(bytearray(len(buffer)))

        result = super().readinto(_b)

        self.dumped += _b[:result].tobytes()

        buffer[:result] = _b[:result]

        return result

    def read(self, *args, **kwargs):
        result = super().read(*args, **kwargs)
        self.dumped += result
        return result


def patch_http_client(raw_func):
    @functools.wraps(raw_func)
    def new_func(self, *args, **kwargs):
        """:type self: http_client.HTTPResponse"""

        if isinstance(self.fp, (HookedBufferedReader, io.BytesIO)):
            # skip!
            return raw_func(self, *args, **kwargs)

        self._raw_fp = self.fp  # type: io.BufferedReader

        # 顺便也记录下IP好了, requests本身也没有记录IP的功能
        try:
            self.source_ip = self._raw_fp.raw._sock.getsockname()
            self.dest_ip = self._raw_fp.raw._sock.getpeername()
        except:
            self.source_ip = None
            self.dest_ip = None

        self.fp = HookedBufferedReader(self._raw_fp.raw)
        self.dumped = self.fp.dumped  # type: bytearray

        return raw_func(self, *args, **kwargs)

    return new_func


def monkey_patch():
    global _already_patched
    if _already_patched or hasattr(http.client.HTTPResponse, "_original_begin"):
        return
    http.client.HTTPResponse._original_begin = http.client.HTTPResponse.begin
    http.client.HTTPResponse.begin = patch_http_client(http.client.HTTPResponse.begin)
    _already_patched = True


def get_raw(resp):
    """:rtype: bytearray"""
    try:
        return resp.raw._original_response.dumped  # type: bytearray
    except:
        return None


def get_body(data):
    """

    :type data: bytearray
    :rtype: bytearray
    """
    pos = data.find(b"\r\n\r\n")
    if pos == -1:
        return bytearray()
    else:
        return data[pos + 4:]


def decode_chunked(data):
    """
    from: http://beezari.livejournal.com/190869.html
    modified for python3 compatibility
    :type data: bytearray
    :rtype: bytearray
    """
    dec_body = bytearray()
    # of the data payload. you can also parse content-length header as well.
    if data.startswith(b"HTTP/"):
        chunked_body = get_body(data)
    else:
        chunked_body = data

    while chunked_body:
        off = int(chunked_body[:chunked_body.find(b"\r\n")], 16)
        if not off:
            break
        chunked_body = chunked_body[chunked_body.find(b"\r\n") + 2:]
        dec_body += chunked_body[:off]
        chunked_body = chunked_body[off + 2:]

    return dec_body


def get_ip(resp):
    """获取请求的source_ip 和 dest_ip"""
    # (source_ip, dest_ip)
    return resp.raw._original_response.source_ip, resp.raw._original_response.dest_ip


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    print("doctest passed")
