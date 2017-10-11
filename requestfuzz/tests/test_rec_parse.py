#!/usr/bin/env python3
# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
from future.backports.urllib import parse
import copy
import json
from requestfuzz import QueryDict
from requestfuzz.recursive_parse import *


def test_basic_form():
    ori = [
        ("a", "1"),
        ("b", "2"),
        ("a", "3"),
        ("d", "4"),
        ("f", ""),
    ]
    ori_text = parse.urlencode(ori)
    root = load(ori_text)

    assert isinstance(root, FormNode)
    assert root.data == QueryDict([('a', '1'), ('b', '2'), ('a', '3'), ('d', '4'), ('f', '')])
    assert root.text == ori_text

    for index, node in enumerate(root.iter_tree()):
        assert isinstance(node, PlainNode)
        assert node.key == ori[index][0]
        assert node.data == ori[index][1]
        assert node.index_in_parent == index


def test_form_modify():
    ori = [
        ("a", "1"),
        ("b", "2"),
        ("a", "3"),
        ("d", "4"),
        ("f", ""),
    ]
    ori_text = parse.urlencode(ori)
    root = load(ori_text)

    root.children[1].reload("foo")  # b=foo

    assert root.text == "a=1&b=foo&a=3&d=4&f="
    assert root.data == QueryDict([('a', '1'), ('b', 'foo'), ('a', '3'), ('d', '4'), ('f', '')])
    assert root.children[1].data == "foo"
    assert root.children[1].index_in_parent == 1


def test_form_fork():
    ori = [
        ("a", "1"),
        ("b", "2"),
        ("a", "3"),
        ("d", "4"),
        ("f", ""),
    ]
    ori_text = parse.urlencode(ori)
    root = load(ori_text)

    # 新树的根节点
    new_root = root.children[1].fork_tree("foo")  # b=foo

    assert new_root.text == "a=1&b=foo&a=3&d=4&f="
    assert new_root.data == QueryDict([('a', '1'), ('b', 'foo'), ('a', '3'), ('d', '4'), ('f', '')])
    assert new_root.children[1].data == "foo"
    assert new_root.children[1].index_in_parent == 1

    # 旧树不发生改变
    assert root.data == QueryDict([('a', '1'), ('b', '2'), ('a', '3'), ('d', '4'), ('f', '')])
    assert root.children[1] is not new_root.children[1]


def test_complex():
    js = {
        "monkey": "cat",
        "aform": parse.urlencode([
            ("choice", 17),
            ("choice", 18),
            ("choice", parse.quote("test+1fsf")),
            ("choice", "ZnNmc2Q="),
            ("json", json.dumps({"chained": "json2", "aaa": "bbb"}))
        ]),
        "foo": ["b", "a", {"b": "c", "d": "e"}, "this=is&a=form"],
        "bar": False,
        "ttt": None,
        "key-with.a-dot": "value-with.a-dot",
        "中文": "中文"
    }
    nested = r"""_callback({})""".format(json.dumps(js, ensure_ascii=False))

    root = load(nested)

    assert isinstance(root, JSONPNode)
    assert str(root["monkey"]) \
           == "PlainNode<key='monkey' parent='<root>' depth=1 data='cat'>"
    assert str(root["bar"]) \
           == "PlainNode<key='bar' parent='<root>' depth=1 data=False>"
    assert str(root["ttt"]) \
           == "PlainNode<key='ttt' parent='<root>' depth=1 data=None>"
    assert str(root["key-with.a-dot"]) \
           == "PlainNode<key='key-with.a-dot' parent='<root>' depth=1 data='value-with.a-dot'>"
    assert str(root["中文"]) == "PlainNode<key='中文' parent='<root>' depth=1 data='中文'>"
    assert str(root["aform"]) \
           == """FormNode<key='aform' parent='<root>' depth=1 data=QueryDict([('choice', '17'), ('choice', '18'), ('choice', 'test%2B1fsf'), ('choice', 'ZnNmc2Q='), ('json', '{"chained": "json2", "aaa": "bbb"}')])>"""
    assert str(root["foo"]) \
           == "JSONNode<key='foo' parent='<root>' depth=1 data=['b', 'a', {'b': 'c', 'd': 'e'}, 'this=is&a=form']>"

    # 测试fork
    new_root = root["aform"]["json"]["aaa"].fork_tree("doge")
    _node = new_root["aform"]["json"]["aaa"]
    assert _node.data == "doge"
    assert _node.parent.data == {'aaa': 'doge', 'chained': 'json2'}
    assert str(_node.parent.parent) \
           == """FormNode<key='aform' parent='<root>' depth=1 data=QueryDict([('choice', '17'), ('choice', '18'), ('choice', 'test%2B1fsf'), ('choice', 'ZnNmc2Q='), ('json', '{"chained": "json2", "aaa": "doge"}')])>"""

    # 测试fork, 同时改变key和value
    new_root = root["aform"]["json"]["aaa"].fork_tree("doge2", key="kite")
    _node = new_root["aform"]["json"]["kite"]
    assert "aaa" not in new_root["aform"]["json"]  # key重命名
    assert _node.data == "doge2"
    assert _node.parent.data == {'kite': 'doge2', 'chained': 'json2'}

    # fork后原有的node不发生改变
    assert str(root["aform"]["json"]["aaa"]) \
           == "PlainNode<key='aaa' parent='json' depth=3 data='bbb'>"
    assert root["aform"]["json"]["aaa"].index_in_parent == 1
    assert root["aform"]["json"]["aaa"].abskey \
           == ('<root>', 'aform#1', 'json#4', 'aaa#1')

    assert str(root["foo"]["2"]) \
           == "JSONNode<key='2' parent='foo' depth=2 data={'b': 'c', 'd': 'e'}>"

    # 遍历叶子
    all_leaves = [
        "monkey",
        "choice", "choice",
        "chained", "aaa", "urlencode", "base64",
        "0", "1", "this",
        "b", "a", "d",
        "bar", "ttt", "key-with.a-dot", "中文",
    ]
    _all_leaves = copy.copy(all_leaves)
    for leaf in root.iter_all_leaves():
        # print(leaf, leaf.abskey)
        _all_leaves.remove(leaf.key)

    assert not _all_leaves


if __name__ == '__main__':
    test_basic_form()
    test_form_modify()
    test_form_fork()
    test_complex()
    print("all tests passed")
