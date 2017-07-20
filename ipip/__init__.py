#!/usr/bin/env python3
# coding: utf-8
from __future__ import unicode_literals, print_function

import logging
import struct
from socket import inet_aton
import os
import collections

logger = logging.getLogger(__name__)

_unpack_V = lambda b: struct.unpack("<L", b)
_unpack_N = lambda b: struct.unpack(">L", b)
_unpack_C = lambda b: struct.unpack("B", b)

_finder_cls = None

IPInfo = collections.namedtuple("IPInfo", (
    "ip",
    "country", "province", "city", "village",
    "isp",
    "lat", "lon",
    "timezone_name", "timezone_offset",
    "postcode", "phone_prefix",
    "country_abbr", "continent"
))


class IP(object):
    offset = 0
    index = 0
    binary = b""
    
    @staticmethod
    def load(file):
        try:
            path = os.path.abspath(file)
            with open(path, "rb") as f:
                IP.binary = f.read()
                IP.offset, = _unpack_N(IP.binary[:4])
                IP.index = IP.binary[4:IP.offset]
        except:
            logger.error("cannot open file %s" % file, exc_info=True)
            raise
    
    @staticmethod
    def find(ip):
        index = IP.index
        offset = IP.offset
        binary = IP.binary
        nip = inet_aton(ip)
        ipdot = ip.split('.')
        if int(ipdot[0]) < 0 or int(ipdot[0]) > 255 or len(ipdot) != 4:
            return None
        
        tmp_offset = int(ipdot[0]) * 4
        start, = _unpack_V(index[tmp_offset:tmp_offset + 4])
        
        index_offset = index_length = 0
        max_comp_len = offset - 1028
        start = start * 8 + 1024
        while start < max_comp_len:
            if index[start:start + 4] >= nip:
                index_offset, = _unpack_V(index[start + 4:start + 7] + b'\x00')
                index_length, = _unpack_C(index[start + 7:start + 8])
                break
            start += 8
        
        if index_offset == 0:
            return None
        
        res_offset = offset + index_offset - 1024
        return binary[res_offset:res_offset + index_length].decode('utf-8')


class IPX(object):
    binary = b""
    index = 0
    offset = 0
    
    @staticmethod
    def load(file):
        try:
            path = os.path.abspath(file)
            with open(path, "rb") as f:
                IPX.binary = f.read()
                IPX.offset, = _unpack_N(IPX.binary[:4])
                IPX.index = IPX.binary[4:IPX.offset]
        except:
            logger.error("IPIP: cannot open file %s" % file, exc_info=True)
            raise
    
    @staticmethod
    def find(ip):
        index = IPX.index
        offset = IPX.offset
        binary = IPX.binary
        nip = inet_aton(ip)
        ipdot = ip.split('.')
        if int(ipdot[0]) < 0 or int(ipdot[0]) > 255 or len(ipdot) != 4:
            return None
        
        tmp_offset = (int(ipdot[0]) * 256 + int(ipdot[1])) * 4
        start, = _unpack_V(index[tmp_offset:tmp_offset + 4])
        
        index_offset = index_length = -1
        max_comp_len = offset - 262144 - 4
        start = start * 9 + 262144
        
        while start < max_comp_len:
            if index[start:start + 4] >= nip:
                index_offset, = _unpack_V(index[start + 4:start + 7] + b'\x00')
                index_length, = _unpack_C(index[start + 8:start + 9])
                break
            start += 9
        
        if index_offset == 0:
            return None
        
        res_offset = offset + index_offset - 262144
        return binary[res_offset:res_offset + index_length].decode('utf-8')


def setup_ipx(file_path=None):
    global _finder_cls
    if file_path is None:
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipip.datx")
    IPX.load(file_path)
    _finder_cls = IPX


def find(ip):
    if _finder_cls is None:
        setup_ipx()
    
    result = _finder_cls.find(ip)
    if result is None:
        return None
    result = [ip] + result.split("\t")
    ip_info = IPInfo(*result)
    return ip_info


if __name__ == '__main__':
    print(find("118.28.8.8"))
    print(find("42.120.74.202"))
    print(find("8.8.8.8"))
    print(find("11.191.47.131"))
