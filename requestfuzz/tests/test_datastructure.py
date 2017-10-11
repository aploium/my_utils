#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six

import pytest

from requestfuzz import OrderedMultiDict


@pytest.mark.skip("暂时无法保留update时的重复key")
def test_update_with_dup_key():
    omd = OrderedMultiDict()
    omd.update(OrderedMultiDict([
        ("a", "1"),
        ("a", "2")
    ]))

    assert omd == OrderedMultiDict([
        ("a", "1"),
        ("a", "2")
    ])
