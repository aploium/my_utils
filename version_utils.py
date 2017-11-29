#!/usr/bin/env python3
# coding=utf-8
"""
用于版本字符串的转换、比较、范围匹配

用法请看 `test__version_range` 这个函数
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future import utils as six
import re
import sys
import operator
from distutils.version import Version as _BaseVersion
from distutils.version import LooseVersion

PY3 = sys.version_info[0] == 3
if PY3:
    string_types = str
else:
    # noinspection PyUnresolvedReferences
    string_types = (unicode, str, basestring)

RE_SPLIT_COMPARISON = re.compile(r"^\s*(<=|>=|<|>|!=|==)\s*([^\s,]+)\s*$")
RE_REMOVE_BLANK = re.compile(r"\s*")
COMPMAP = {"<": operator.lt, "<=": operator.le, "==": operator.eq,
           ">": operator.gt, ">=": operator.ge, "!=": operator.ne}
COMPMAP_REVERSE = {v: k for k, v in COMPMAP.items()}


def to_version(version):
    if isinstance(version, string_types):
        return Version(remove_blank(version))
    else:
        return version


def remove_blank(txt):
    """移除空白字符"""
    return RE_REMOVE_BLANK.sub("", txt)


class Version(LooseVersion):
    pass


class VersionCond(object):
    """

    >=1.2
    <2.5
    """

    def __init__(self, op, version):
        self.version = to_version(version)

        if isinstance(op, string_types):
            op = COMPMAP[op]
        self.op = op

    def match(self, version):
        if self.version.vstring == 'all':
            return True
        if not version or not isinstance(version, (string_types, Version)):
            return False
        version = to_version(version)
        return self.op(version, self.version)

    @classmethod
    def from_str(cls, cond_str):
        cond_str = remove_blank(cond_str)
        m = RE_SPLIT_COMPARISON.search(cond_str)
        if m is not None:
            op = m.group(1)
            version = m.group(2)
        else:
            # 若没有找到操作符, 则认为需要完全匹配版本串
            op = "=="
            version = cond_str

        return cls(op, version)

    def to_str(self):
        if self.op == operator.eq:
            op_str = ''  # 省略等号
        else:
            op_str = COMPMAP_REVERSE[self.op]
        return "{}{}".format(op_str, self.version.vstring)

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.to_str())


class CondGroup(object):
    """

    >=1.5,<1.9
    """

    def __init__(self, conds):
        if isinstance(conds, VersionCond):
            self.conds = [conds]
        elif isinstance(conds, six.string_types):
            self.conds = [VersionCond.from_str(x) for x in conds.split(',')]
        elif not conds:
            self.conds = []
        else:
            self.conds = [VersionCond(op, version) for op, version in conds]

    def match(self, version):
        version = to_version(version)

        for cond in self.conds:
            if not cond.match(version):
                return False
        return True

    def to_str(self):
        if self.conds is None:
            return "all"
        return ",".join(c.to_str() for c in self.conds)

    def __str__(self):
        return self.to_str()


class VersionRange(object):
    def __init__(self, ranges):
        if isinstance(ranges, string_types):
            self.ranges = [CondGroup(x) for x in ranges.split('|')]
        elif isinstance(ranges, (list, tuple)):
            self.ranges = [CondGroup(x) for x in ranges]
        elif not ranges:
            self.ranges = []
        else:
            raise TypeError('unknown ranges type')

    def match(self, version):
        if not self.ranges:
            return True
        version = to_version(version)
        for cond_group in self.ranges:
            if cond_group.match(version):
                return True
        return False

    def to_str(self):
        return "|".join(cg.to_str() for cg in self.ranges)

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.to_str())


def test_version_cond():
    for cond in (
            VersionCond(">", "1.5"),
            VersionCond.from_str(">1.5"),
            VersionCond.from_str(">=1.5"),
            VersionCond.from_str(">=1.9"),
            VersionCond.from_str(">=1.10"),
    ):
        assert cond.match("10.0")
        assert cond.match("1.10")
        assert cond.match("1.4.9a1") is False
        assert cond.match("0.9.1p7") is False

    for cond in (
            VersionCond("<", "1.5"),
            VersionCond.from_str("<1.5 "),
            VersionCond.from_str("<= 1.5"),
            VersionCond.from_str("<= 1.9"),
            VersionCond.from_str("<=1.4.9b1"),
            VersionCond.from_str(" <1.4.9b1"),
            VersionCond.from_str("<= 1.4.10 "),
            VersionCond.from_str(" <= 1.4.9a1 "),
    ):
        assert cond.match("10.0") is False
        assert cond.match("1.10") is False
        assert cond.match("1.4.9a1")
        assert cond.match("0.9.1p7")

    for cond in (
            VersionCond("==", "1.4"),
            VersionCond.from_str(" 1.4 "),
            VersionCond.from_str("== 1.4"),
            VersionCond.from_str("!=1.5"),
    ):
        assert cond.match("1.4")
        assert cond.match("1.5") is False

    assert VersionCond.from_str('all').match("any thing!")


def test_version_range():
    for vr in (
            VersionRange(["1.4", "==1.4.1", "1.4.2", "1.5.0", "1.5.1", "1.5.2", "1.6"]),
            VersionRange([">=1.4, <=1.4.2 ", " >=1.5, <1.5.3 ", "==1.6"]),  # 允许空格
            VersionRange([">=1.4, <=1.4.1 ", "1.4.2", " >=1.5, <1.5.3 ", "1.6"]),
            VersionRange(">=1.4, <=1.4.1 |1.4.2 | >=1.5, <1.5.3 |1.6"),  # 字符串
            VersionRange(">=1.4,<=1.4.1|1.4.2|>=1.5,<1.5.3|1.6"),
            VersionRange("!=1.4.3,!=1.2.3"),
            VersionRange(["!=1.4.3, !=1.2.3"]),
    ):
        assert vr.match("1.4.1")
        assert vr.match("1.4.2")
        assert vr.match("1.4.3") is False
        assert vr.match("1.2.3") is False
        assert vr.match("1.5.0 ")  # 允许空格
        assert vr.match("1.5.1")
        assert vr.match(" 1.5.2")
        assert vr.match("1.6")
        assert vr.match(Version("1.6"))

    vr = VersionRange([">1.5, <1.11", "2.5"])
    assert vr.match("1.10")
    assert vr.match("2.5")
    assert vr.match("1.10.b")  # 允许各种奇怪的版本号
    assert vr.match("1.10+")
    assert vr.match("1.10c")
    assert vr.match("1.9c")
    assert vr.match("1.9.x")
    assert vr.match("1.9.*")
    assert vr.match("1.4z") is False
    assert vr.match("2016") is False
    assert vr.match(None) is False
    assert vr.match(1.11) is False
    assert vr.match(object()) is False

    vr = VersionRange(">=2016, <2017")
    assert vr.match("2016春节版")
    vr = VersionRange(">=2016, <2017.1")
    assert vr.match("2016春节版")

    # all 和 None 表示匹配所有东西
    for vr in (
            VersionRange(None),
            VersionRange([None]),
            VersionRange("all"),
            VersionRange(["all"]),
    ):
        assert vr.match("match anything!")

    # 对字符串对转换
    vr = VersionRange([">=1.4, <=1.4.1 ", "1.4.2", "==1.4.3", " >=1.5, <1.5.3 ", "1.6"])
    assert vr.to_str() == '>=1.4,<=1.4.1|1.4.2|1.4.3|>=1.5,<1.5.3|1.6'
    vr = VersionRange('>=1.4 , <= 1.4.1 | 1.4.2 | >= 1.5 , < 1.5.3 | 1.6 ')  # space
    assert vr.to_str() == '>=1.4,<=1.4.1|1.4.2|>=1.5,<1.5.3|1.6'


if __name__ == "__main__":
    test_version_cond()
    test_version_range()

    print("all tests passed!")
