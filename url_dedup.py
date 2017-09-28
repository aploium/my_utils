#!/usr/bin/env python3
# coding=utf-8
"""
提供带有归一化的 url 去重功能

所有流量生成FZ类，进行参数循环解析生成参数list，去除所有无用参数
使用uri与参数list的key作为标识去重
相同的uri与完全相同的参数list的key的FZ为同一个请求
FZ 输出，重新入库

Requirements:
    pybloom-live
    future
    
    pybloomfiltermmap [可选, 仅在linux下有, 能快很多]
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future import utils as six

if six.PY3:
    from urllib import parse
else:
    from future.backports.urllib import parse

try:
    from pybloomfilter import BloomFilter
except ImportError:
    from pybloom_live import BloomFilter


class UrlDedup(object):
    """
    带有归一化的 url 去重功能
    
    白名单和黑名单:
        会保留白名单中参数的value, 例如 "action=put" 在常规情况下会变成 action=
          而在白名单内的, 则不会被移除value, 即 "action=put" 会完整保留
        黑名单中的参数将会被丢弃
    
    Examples:
        >>> ud = UrlDedup()
        >>> ud.occurs("http://cat.com/foo")
        False
        >>> ud.occurs("http://cat.com/foo") # 第二次出现返回 True
        True
        >>> ud.occurs("http://cat.com/foo?id=1") # 没出现过的参数
        False
        >>> ud.occurs("http://cat.com/foo?id=233") # 参数key相同
        True
    
    500w, err=0.001 的情况下, 占用内存大约 8MB
    """
    
    WHITELIST = frozenset(["action", "Action", "method"])
    BLACKLIST = frozenset([
        'spm', '_spm', '__preventCache', '_t',
        'timestamp', '_timestamp', '__timestamp',
        '_'
    ])
    
    def __init__(self, capacity=5000000, err_rate=0.001,
                 whitelist=WHITELIST, blacklist=BLACKLIST,
                 ):
        self.bloom = BloomFilter(capacity, err_rate)
        self.whitelist = whitelist
        self.blacklist = blacklist
    
    def _normalize(self, url):
        """
        将url转换为可用于bloom的形式
        
        会去掉query中的 value, 排序key, 并移除 fragment
        
        Examples:
            http://cat.com/foo?z=x&a=b&c=d   排序并移除value
            --> http://cat.com/foo?a=&c=&z=
            
            http://cat.com/foo#cat   丢弃fragment
            --> http://cat.com/foo
            
            http://cat.com/foo    保持原样
            --> http://cat.com/foo
            
            由于query中的key会发生排序, 所以下面两个url是 *等效* 的
                http://cat.com/foo?a=1&b=2
                http://cat.com/foo?b=2&a=1
            
            不区分大小写, 所以以下两个是 *不同* 的
                http://cat.com/foo?A=1
                http://cat.com/foo?A=2
            
            黑白名单(action为白名单, spm黑名单)
                http://cat.com/foo?action=put&spm=12345
                --> http://cat.com/foo?action=put
        """
        try:
            _sp = parse.urlsplit(url)
        except:  # 解析url失败, 原样返回
            return url
        
        if not _sp.query:
            if not _sp.fragment:
                return url
            else:
                # 移除fragment
                return parse.urlunsplit((_sp.scheme, _sp.netloc, _sp.path, "", ""))
        
        # ---- 处理query -----
        try:
            query = parse.parse_qsl(_sp.query, True)
        except:
            return url
        query.sort()
        
        normalized_query = []
        
        for key, value in query:
            if key in self.blacklist:
                continue
            elif key in self.whitelist:
                pass
            else:
                value = ""
            normalized_query.append((key, value))
        
        normalized_query = parse.urlencode(normalized_query)
        
        return parse.urlunsplit((_sp.scheme, _sp.netloc, _sp.path, normalized_query, ""))
    
    def occurs(self, url, auto_add=True):
        """
        给定一个url, 返回此 url 在以前有没有出现过
        并自动将此 url 记录为 "已出现"
        
        例子见上面的文档
        
        Returns:
            bool: 此url是否出现过
        """
        normalized_url = self._normalize(url)
        if isinstance(url, six.text_type):
            normalized_url = normalized_url.encode("UTF-8")
        
        if auto_add:
            return self.bloom.add(normalized_url)
        else:
            return normalized_url in self.bloom
    
    def __contains__(self, url):
        return self.occurs(url, auto_add=False)
    
    def add(self, url):
        return self.occurs(url)


def test_url_dedup():
    ud = UrlDedup()
    
    # 基础测试
    assert ud.occurs("http://cat.com") is False
    assert ud.occurs("http://cat.com") is True
    assert ud.occurs("http://cat.com/foo") is False
    assert ud.occurs("http://cat.com/foo") is True
    assert ud.occurs("http://cat.com/foo#frag") is True  # 剔除frag
    assert ud.occurs("http://cat.com") is True
    
    # 测试query
    assert ud.occurs("http://cat.com/?a=1&b=2&c=3") is False
    assert ud.occurs("http://cat.com/?a=4&b=5&c=") is True  # 相同的query key
    assert ud.occurs("http://cat.com/?A=1&b=2&c=3") is False  # 区分大小写
    assert ud.occurs("http://cat.com/?b=1&a=2&c=3") is True  # 顺序无关
    assert ud.occurs("http://cat.com/?a=1&b=2") is False  # 少了一个c, 被认为是不同的
    assert ud.occurs("https://cat.com/?a=1&b=2&c=3") is False  # http和https
    assert ud.occurs("https://cat.com/?a=1&b=2&c=3#aaa") is True  # 剔除frag
    assert ud.occurs("https://cat.com/path?a=1&b=2&c=3") is False  # 不同的path
    
    # 测试白名单
    assert ud._normalize("http://cat.com/?action=put&id=1") \
           == "http://cat.com/?action=put&id="  # 完整保留 action=put
    assert ud.occurs("http://cat.com/?action=put&id=1") is False  # 其中action是白名单
    assert ud.occurs("http://cat.com/?action=get&id=1") is False  # 不同的action被认为是不同的
    assert ud.occurs("http://cat.com/?action=put&id=2") is True  # 改变action以外的参数则是相同的
    
    # 测试黑名单
    assert ud._normalize("http://cat.com/?spm=1234&id=1") \
           == "http://cat.com/?id="  # spm被吃掉了
    assert ud.occurs("http://cat.com/?spm=1234&id=1") is False
    assert ud.occurs("http://cat.com/?id=1") is True  # 移除spm, 也是出现过的
    assert ud.occurs("http://cat.com/?_t=777&id=1") is True  # 加上另一个黑名单参数
    assert ud.occurs("http://cat.com/?_t=888&id=1&spm=999") is True
    
    # 测试参数顺序的重排
    assert ud._normalize("http://cat.com/?y=2&x=1&z=3") \
           == "http://cat.com/?x=&y=&z="
    assert ud.occurs("http://cat.com/?x=1&y=2&z=3") is False
    assert ud.occurs("http://cat.com/?y=1&x=2&z=3") is True  # 更换参数顺序
    
    # 测试大量url能否判断
    _total = 100000
    _sum = sum(ud.occurs("http://dog.com/?id_{}=1".format(i)) for i in range(_total))
    assert _sum < _total / 500.0, _sum / _total  # 允许很少量的假阳性
    for i in range(_total):
        assert ud.occurs("http://dog.com/?id_{}=1".format(i)) is True
    
    assert ud.occurs("http://cat.com/?a=4&b=5&c=") is True  # 最后测试一下之前出现的


if __name__ == '__main__':
    test_url_dedup()
    print("all tests passed!")
