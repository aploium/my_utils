# coding=utf-8
"""
用于版本字符串的转换、比较、范围匹配

用法请看 `test__version_range` 这个函数

依赖：
    future
    distutils

@aploium
MIT License
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future import utils as six
import re
import sys
import operator
from distutils.version import LooseVersion as _LooseVersion

RE_SPLIT_COMPARISON = re.compile(r"^\s*(<=|>=|<|>|!=|==)\s*([^\s,]+)\s*$")
RE_REMOVE_BLANK = re.compile(r"\s*")
COMPMAP = {"<": operator.lt, "<=": operator.le, "==": operator.eq,
           ">": operator.gt, ">=": operator.ge, "!=": operator.ne}
COMPMAP_REVERSE = {v: k for k, v in COMPMAP.items()}


def to_version(version):
    if isinstance(version, six.string_types):
        return Version(remove_blank(version))
    else:
        return version


def remove_blank(txt):
    """移除空白字符"""
    return RE_REMOVE_BLANK.sub("", txt)


class Version(_LooseVersion):
    def _cmp(self, other):
        if isinstance(other, str):
            other = Version(other)
        try:
            if self.version == other.version:
                return 0
            if self.version < other.version:
                return -1
            if self.version > other.version:
                return 1
        except TypeError:
            # issues #2
            #   没有可靠的办法比较字符串版本号和数字版本号的大小,
            #   但是为了避免抛出意外的错误, fallback到简陋的字符串比较
            if self.vstring == other.vstring:
                return 0
            if self.vstring < other.vstring:
                return -1
            if self.vstring > other.vstring:
                return 1


@six.python_2_unicode_compatible
class VersionCond(object):
    """

    >=1.2
    <2.5
    """

    def __init__(self, op, version):
        self.version = to_version(version)

        if isinstance(op, six.string_types):
            op = COMPMAP[op]
        self.op = op

    def match(self, version):
        if self.version.vstring == 'all':
            return True
        if not version or not isinstance(version, (six.string_types, Version)):
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
        return "{}({})".format(self.__class__.__name__, repr(self.to_str()))


@six.python_2_unicode_compatible
class CondGroup(object):
    """

    >=1.5,<1.9
    """

    def __init__(self, conds):
        if isinstance(conds, CondGroup):
            self.conds = conds.conds
        elif isinstance(conds, VersionCond):
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

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.to_str()))


@six.python_2_unicode_compatible
class VersionRange(object):
    def __init__(self, ranges):
        if isinstance(ranges, six.string_types):
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
        return "{}({})".format(self.__class__.__name__, repr(self.to_str()))

    def __eq__(self, other):
        if isinstance(other, VersionRange):
            return self.to_str() == other.to_str()
        elif isinstance(other, six.string_types):
            return self.to_str() == other
        else:
            return False


def _internal_guess_range(versions):
    """
    供下面 guess_range_from_versions() 内部调用，只会分成一段

    Args:
        versions (list[Version])
    """
    lowest = highest = versions[0]
    for version in versions[1:]:
        if version < lowest:
            lowest = version
        elif version > highest:
            highest = version

    return lowest, highest


def guess_range(versions, digits=2):
    """
    根据一系列离散的版本猜测版本范围
    会把 group_digits 位的版本分为同一段

    Examples：
        (digits=1) "1.1|1.2|1.3|1.4" --> ">=1.1,<=1.4"
        (digits=1) "1.1|1.2|1.3|1.4|2.1|2.2|2.3" --> ">=1.1,<=1.4|>=2.1,<=2.3"

        '1.1.1|1.1.2|1.1.3|1.2|1.2.4|2.0|2.0.2|3.0'
         --> '>=1.1.1,<=1.1.3|>=1.2,<=1.2.4|>=2.0,<=2.0.2|3.0'


    Args:
        versions (list[str]|str): 一系列离散的版本号
        digits (int): 将最高几位作为一组

    Returns:
        VersionRange
    """
    if isinstance(versions, six.string_types):
        versions = [Version(x) for x in versions.split('|')]
    else:
        versions = [Version(x) for x in versions]

    versions.sort()

    if not versions:
        raise ValueError('must given at least one version')

    sections = []
    group_buff = [versions[0]]

    for version in versions[1:]:
        if version.version[:digits] == group_buff[0].version[:digits]:
            group_buff.append(version)
        else:
            sections.append(_internal_guess_range(group_buff))
            group_buff = [version]
    # 最后一组
    sections.append(_internal_guess_range(group_buff))

    version_ranges = []
    for low, high in sections:
        if low == high:
            cg = low.vstring
        else:
            cg = ">={},<={}".format(low, high)
        version_ranges.append(cg)

    vr = VersionRange(version_ranges)

    return vr

# -----------------------------------------------------
# ------------------- BEGIN   TESTS -------------------
# -----------------------------------------------------

def test_version():
    v1 = Version('1.4.9.1')
    v2 = Version('1.4.9a1')
    # 这种比较是不靠谱的, 但是没有可靠的方法
    #   see issues#2
    assert v2 > v1

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
    assert vr == '>=1.4,<=1.4.1|1.4.2|>=1.5,<1.5.3|1.6'
    assert vr == VersionRange('>=1.4,<=1.4.1|1.4.2|>=1.5,<1.5.3|1.6')


def test_range_guess():
    vr = guess_range("1.1|1.2|1.3|1.4", digits=1)
    assert vr == '>=1.1,<=1.4'

    vr = guess_range("1.1|1.2|1.3|1.4|2.1|2.2|2.3", digits=1)
    assert vr == '>=1.1,<=1.4|>=2.1,<=2.3'

    vr = guess_range('1.1.1|1.1.2|1.1.3|1.2|1.2.4|2.0|2.0.2|3.0')
    assert vr == '>=1.1.1,<=1.1.3|>=1.2,<=1.2.4|>=2.0,<=2.0.2|3.0'

    vr = guess_range('1.1')
    assert vr == '1.1'

    vr = guess_range('1.1|2.0|3.0')
    assert vr == '1.1|2.0|3.0'

    vr = guess_range('1.1.1|1.1.2|1.1.3|1.2|1.2.4|2.0|2.0.2|3.0'.split("|"))
    assert vr == '>=1.1.1,<=1.1.3|>=1.2,<=1.2.4|>=2.0,<=2.0.2|3.0'

    # 允许乱序
    vr = guess_range(['2.0.2', '1.1.2', '1.2.4', '1.1.3', '1.2', '3.0', '1.1.1', '2.0'])
    assert vr == '>=1.1.1,<=1.1.3|>=1.2,<=1.2.4|>=2.0,<=2.0.2|3.0'


if __name__ == "__main__":
    test_version()
    test_version_cond()
    test_version_range()
    test_range_guess()

    print("all tests passed!")
