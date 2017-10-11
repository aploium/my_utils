# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *
import six
import collections
import json
import string
import copy
import cgi
import weakref
import base64
import re
from io import BytesIO

if six.PY3:
    from urllib import parse
else:
    from future.backports.urllib import parse

from .datastructure import QueryDict, to_querydict
from . import utils

__all__ = ["BaseNode", "FormNode", "JSONNode", "JSONPNode", "PlainNode",
           "UrlEncodeNode", "Base64EncodeNode", "load", "ENABLED_NODES"]


def _is_json_iterable(obj):
    if isinstance(obj, six.string_types) \
            or isinstance(obj, six.integer_types) \
            or obj in (True, False, None):
        return False
    elif utils.like_dict(obj) or utils.like_list(obj):
        return True
    else:
        raise TypeError("type: {} is not an iterable json type".format(type(obj)))


def _key_concat(parent, key):
    """

    Args:
        parent (tuple):
        key (str):

    Returns:
        tuple:
    """
    if not parent:
        return key
    else:
        if isinstance(key, list):
            key = tuple(key)
        elif isinstance(key, six.string_types):
            key = (key,)
        return parent + key


def recursive_iter(js, parent=None):
    """递归遍历json中的key-value, 深度优先"""
    if not _is_json_iterable(js):
        yield None, js

    elif utils.like_dict(js):
        for k, v in js.items():
            # 类似 "foo.bar.cat" 的key的绝对路径
            abs_key = _key_concat(parent, k)

            yield abs_key, v

    elif utils.like_list(js):

        for index, v in enumerate(js):
            abs_key = _key_concat(parent, "{}".format(index))  # <list-index-{}>"{}".format(index)

            yield abs_key, v

    else:
        # you should never be here!
        raise TypeError("type: {} is not an iterable json type".format(type(js)))


def parse_multipart(data, content_type):
    """

    Args:
        data (bytes): multipart的二进制
        content_type (headers中的 Content-Type):
            里面包含切分multipart所需的 boundary
            一般像这样:
            multipart/form-data; boundary=----WebKitFormBoundaryEW35oPYWK6qwibcP

    Returns:
        dict[str, cgi.FieldStorage] | QueryDict: key-value
    """
    environ = {
        "QUERY_STRING": "",  # 需要有, 但是没实际作用
        "REQUEST_METHOD": "POST",  # 同上, 必须为POST
        "CONTENT_TYPE": content_type,  # 里面需要包含 boundary
        "CONTENT_LENGTH": len(data),
    }
    fs = cgi.FieldStorage(
        fp=BytesIO(data),
        environ=environ,
        keep_blank_values=True,
    )
    data = fs.list or []
    multipart = QueryDict()
    for item in data:  # type: cgi.FieldStorage
        if item.filename:
            multipart[item.name] = item
        else:
            multipart[item.name] = item.value

    return multipart


def split_multipart(multipart):
    """
    从multipart中切分出普通参数和文件

    Args:
        multipart(dict[str, str|cgi.FieldStorage]): multipart的dict
    Returns:
        tuple[QueryDict, dict[str, cgi.FieldStorage]]:
            两个字典: form, files  分别是 multipart 中的普通form参数和文件
    """
    form = QueryDict()
    files = QueryDict()
    for name, item in multipart.items():
        if isinstance(item, cgi.FieldStorage):
            files[name] = item
        else:
            form[name] = item
    return form, files


@six.python_2_unicode_compatible
class BaseNode(object):
    """
    节点树

    Args:
        parent(BaseNode|None): 父节点
        children(list[BaseNode]):
            叶子结点, 如果是 None 的话表示尚未执行叶子结点的生成
              如果是 list (即视为空list) 表示已经执行过叶子结点的生成
              这有助于进行lazy的叶子结点计算
            允许对它进行直接的修改, 例如删除一些不需要的节点

    Methods:
        text(str): property, 整棵树的文本表示
    """
    type = "base"

    def __init__(self, data,
                 parent=None, text=None,
                 key=None, index_in_parent=None):
        """
        Args:
            data(QueryDict): 解析后的data
            parent(BaseNode): 父节点
            key(str): 这个node在parent中的key名
        """
        self.data = data

        self.key = key if parent else "<root>"
        self._index_in_parent = index_in_parent

        self._text_cache = text or None
        self.children = None  # type: list[BaseNode]
        self.parent = parent

    def refresh_children(self):
        """
        根据data计算并生成子节点, 与 refresh_data() 是相反的操作
        data --> children

        注意: 只生成一层子节点, 重建整棵树需要调用 gen_tree()
        """
        raise NotImplementedError

    def refresh_data(self):
        """
        根据children重新生成data, 与 refresh_children() 是相反的操作
        children --> data

        把子节点的修改应用到根节点(整棵树)上
        修改子节点后需要对根调用 .refresh_data()

        此操作是深度优先递归进行的
        """
        raise NotImplementedError

    def rebuild_text(self):
        """
        根据data生成text
        """
        raise NotImplementedError

    @property
    def text(self):
        if self._text_cache is None:
            self.rebuild_text()

        return self._text_cache

    @text.setter
    def text(self, value):
        if not isinstance(self, PlainNode):
            raise NotImplementedError

        self.data = value
        self.rebuild_text()

        parent_node = self.parent
        while parent_node is not None:
            parent_node.refresh_data()
            parent_node.rebuild_text()
            parent_node = parent_node.parent

    @property
    def index_in_parent(self):
        """
        返回自身在父节点中的序号
        若不存在或没有父节点则返回 -1

        如果没有人为设置, 则第一次调用时会尝试自动获取这个序号
        序号缓存在 self._index_in_parent 中

        Returns:
            int
        """
        if self.parent is None:
            return -1

        if self._index_in_parent is None:
            # 自动寻找自身在父节点中的位置
            self._index_in_parent = self.parent.children.index(self)

        return self._index_in_parent

    @index_in_parent.setter
    def index_in_parent(self, value):
        self._index_in_parent = value

    @property
    def depth(self):
        if self.parent is None:
            return 0
        else:
            return self.parent.depth + 1

    @property
    def root(self):
        """返回此节点的根节点"""
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    def reload(self, value, key=NotImplemented, plain=True):
        if key is NotImplemented:
            key = self.key

        if not plain:
            factory = find_proper_node
        else:
            factory = PlainNode
        new_node = factory(
            value, key=key, parent=self.parent,
            index_in_parent=self.index_in_parent,
        )
        new_node.gen_tree()

        current_node = new_node
        parent_node = new_node.parent

        while parent_node is not None:
            parent_node.children[current_node.index_in_parent] = current_node
            parent_node.refresh_data()
            parent_node.rebuild_text()

            current_node = parent_node
            parent_node = parent_node.parent

        return new_node

    def copy(self):
        """生成此节点及以下树的副本"""
        new = copy.copy(self)
        new.gen_tree()
        return new

    def fork_tree(self, value, **kwargs):
        """
        生成树的副本, 并在新树中的对应节点应用修改
        对原树不做修改

        Returns:
            BaseNode: 返回新树的根节点
        """
        new_root = self.root.copy()

        # 修改新树中此节点对应的节点
        my_mirror = new_root.get_by_abskey(self.abskey)
        my_mirror.reload(value, **kwargs)

        return new_root

    def gen_tree(self):
        """计算并生成整棵树
        等效于递归生成子节点
        """
        self.refresh_children()
        self.rebuild_text()
        for child in self.children:
            child.gen_tree()

    def get_by_abskey(self, abskey):
        """在树中根据 abskey 获取子节点"""

        if self.abskey == abskey:
            return self

        for node in self.children:
            if abskey[:len(node.abskey)] == node.abskey:
                return node.get_by_abskey(abskey)

        raise KeyError("key {} not found".format(abskey))

    def iter_all_leaves(self):
        """
        广度优先遍历树中的所有叶子结点

        Yields:
            PlainNode: 各个节点, 所有叶子结点总是 PlainNode
        """
        for node in self.iter_tree():
            if isinstance(node, PlainNode):
                yield node

    def iter_tree(self):
        """
        广度优先遍历整棵树

        Yields:
            BaseNode: 各个节点, 所有叶子结点总是 PlainNode
        """
        if self.children is None:
            # lazy 生成树
            self.gen_tree()

        # pycharm: 这里的warning是pycharm的bug, 下同
        for child in self.children:
            yield child

        for child in self.children:
            # 等效于 `yield from child.iter_tree()`
            #   不过py2不支持这个这个语法
            for ch in child.iter_tree():
                yield ch

    @property
    def abskey(self):
        """
        返回相对于根的绝对key路径
        此绝对路径是一个 tuple

        Examples:
            ("<root>", "foo#1", "bar#7", "#3")
        """
        if self.parent is None:
            return ("<root>",)
        else:
            return _key_concat(
                self.parent.abskey,
                "{}#{}".format(self.key, self.index_in_parent)
            )  # , escape=False)

    def __getitem__(self, key):
        for child in self.children:
            if child.key == key:
                return child
        raise KeyError("key {} not found".format(key))

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        return iter(self.iter_tree())

    def __str__(self):
        return "{klass}<key={key} parent={parent} depth={depth} data={data}>".format(
            klass=self.__class__.__name__,
            key=repr(self.key),
            parent=repr(self.parent.key) if self.parent else None,
            depth=self.depth,
            data=repr(self.data),
        )

    __repr__ = __str__

    @classmethod
    def load(cls, data, **kwargs):
        """
        尝试加载data

        Returns:
            None|BaseNode:
                如果不合法, 则返回 None (预期内的加载失败不抛出异常)
                如果合法, 则返回一个自身的实例
        """
        return cls(data, **kwargs)


class FormNode(BaseNode):
    type = "form"

    def refresh_children(self):
        self.children = []
        for key, data in self.data.items():
            child = find_proper_node(data, key=key, parent=self)
            self.children.append(child)

    def refresh_data(self):
        data = [(child.key, child.text) for child in self.children]
        self.data = to_querydict(data)

    def rebuild_text(self):
        self._text_cache = parse.urlencode(self.data)

    @classmethod
    def load(cls, data, **meta):
        """

        Examples:
            >>> form_str = r'cat=233&foo=bar'
            >>> node = FormNode.load(form_str)
            >>> node.data
            QueryDict([('cat', '233'), ('foo', 'bar')])
            >>> node.children()
            (ChildNode(key='cat', data='233', depth=1),
             ChildNode(key='foo', data='bar', depth=1))

        """
        if not isinstance(data, six.string_types):
            return None

        try:
            data = utils.ensure_unicode(data)
        except:
            return None

        if not ("=" in data
                and "&" in data
                or data.count("=") == 1
                ):
            return None

        data = utils.ensure_unicode(data)
        try:
            query = to_querydict(data)
        except:
            return None
        else:
            return super(FormNode, cls).load(query, text=data, **meta)


class JSONNode(BaseNode):
    type = "json"

    def refresh_children(self):
        self.children = []
        for key, data in recursive_iter(self.data):
            child = find_proper_node(data, key=key, parent=self)
            self.children.append(child)

    def refresh_data(self):
        if utils.like_dict(self.data):
            self.data = {}
            for child in self.children:
                if isinstance(child, JSONNode):
                    self.data[child.key] = child.data
                else:
                    self.data[child.key] = child.text
        else:
            self.data = []
            for child in self.children:
                if isinstance(child, JSONNode):
                    self.data.append(child.data)
                else:
                    self.data.append(child.text)

    def rebuild_text(self):
        self._text_cache = json.dumps(self.data, sort_keys=False, ensure_ascii=False)

    @classmethod
    def load(cls, data, **meta):
        """

        Examples:
            >>> js_str = r'{"cat":"dog","x":["1","2",{"x":false}]}'
            >>> node = JSONNode.load(js_str)
            >>> node.data
            {'cat': 'dog', 'x': ['1', '2', {'x': False}]}
            >>> node.children()
            (ChildNode(key='cat', data='dog', depth=1),
             ChildNode(key=0, data='1', depth=1),
             ChildNode(key=1, data='2', depth=1),
             ChildNode(key='x', data=False, depth=1))

        """
        # 如果传入的是字符串
        if isinstance(data, six.string_types):
            try:
                data = utils.ensure_unicode(data)
            except:
                return None

            data = data.strip()  # 去除前后空格

            # 初步判断它是不是json
            if '"' not in data:
                return None
            if not (data.startswith("{") and data.endswith("}") and ":" in data
                    or data.startswith("[") and data.endswith("]")
                    ):
                return None

            # 大概是json, 尝试解析
            data = utils.ensure_unicode(data)
            try:
                data_json = json.loads(data)
            except:
                return None

        elif utils.like_dict(data) or utils.like_list(data):
            # 传进来的本来就是json, 不进一步处理
            data_json = data

        else:
            return None  # 未知格式

        return super(JSONNode, cls).load(data_json, **meta)


class JSONPNode(JSONNode):
    type = "jsonp"

    _JSONP_PREFIX_CHARS = set(string.ascii_letters + string.digits + "_")

    def __init__(self, data, prefix=None, suffix=None, **kwargs):
        self.prefix = prefix
        self.suffix = suffix
        super(JSONPNode, self).__init__(data, **kwargs)

    def rebuild_text(self):
        self._text_cache = "{}{}{}".format(
            self.prefix,
            json.dumps(self.data, sort_keys=False, ensure_ascii=False),
            self.suffix
        )

    @classmethod
    def load(cls, data, **meta):
        """

        Examples:
            >>> jp_str = '_callback({"cat":"dog","x":["1","2",{"x":false}]})'
            >>> node = JSONPNode.load(jp_str)
            >>> node.data
            {'cat': 'dog', 'x': ['1', '2', {'x': False}]}

        """
        if not isinstance(data, six.string_types):
            return None

        try:
            data = utils.ensure_unicode(data)
        except:
            return None

        data = data.strip()
        if not data.endswith(")") and not data.endswith(");"):
            return None

        # 验证是 callback(.....) 的格式
        lpos = data.find("(")
        if lpos == -1:
            return None
        if set(data[:lpos]).difference(cls._JSONP_PREFIX_CHARS):
            return None

        rpos = data.rfind(")")

        json_str = data[lpos + 1:rpos]  # jsonp里的json本体

        meta["prefix"] = data[:lpos + 1]
        meta["suffix"] = data[rpos:]

        return super(JSONPNode, cls).load(json_str, **meta)


class UrlEncodeNode(BaseNode):
    """经过urlencode的node"""
    type = "urlencode"

    def refresh_data(self):
        self.data = self.children[0].text

    def rebuild_text(self):
        self._text_cache = parse.quote(self.data)

    def refresh_children(self):
        self.children = [
            find_proper_node(self.data, key="urlencode", parent=self)]

    @classmethod
    def load(cls, data, **kwargs):
        if not isinstance(data, six.string_types):
            return None
        # 判断是否为urlencode
        try:
            data = utils.ensure_unicode(data)
            if '%' not in data:
                return None

            if parse.quote(parse.unquote(data)) != data:
                return None
        except:
            return None

        decoded_data = parse.unquote(data)

        return super(UrlEncodeNode, cls).load(decoded_data, text=data, **kwargs)


class Base64EncodeNode(BaseNode):
    """经过base64的node"""
    type = "base64"

    def refresh_data(self):
        self.data = self.children[0].text

    def rebuild_text(self):
        _new = self.data
        if isinstance(_new, six.text_type):  # sentry #1914
            _new = _new.encode("utf-8")
        _new = base64.b64encode(_new)
        if isinstance(_new, six.binary_type):
            _new = _new.decode("ascii")
        self._text_cache = _new

    def refresh_children(self):
        self.children = [
            find_proper_node(self.data, key="base64", parent=self)]

    @classmethod
    def load(cls, data, **kwargs):
        if not isinstance(data, six.string_types):
            return None

        try:
            data = utils.ensure_unicode(data)
        except:
            return None

        if not re.match(r'^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)$', data):
            return None

        # 判断是否为base64
        try:
            _new = base64.b64encode(base64.b64decode(data))
            if six.PY3:
                _new = _new.decode("ascii")
            if _new != data:
                return None
            decoded_data = base64.b64decode(data)
            if six.PY3:
                decoded_data = decoded_data.decode("utf-8")

                # TODO 可以进一步判断是不是base64
        except Exception as e:
            return None

        return super(Base64EncodeNode, cls).load(decoded_data, text=data, **kwargs)


class PlainNode(BaseNode):
    """纯文本的node"""
    type = "plain"

    def refresh_data(self):
        pass

    def rebuild_text(self):
        self._text_cache = self.data

    def refresh_children(self):
        self.children = []  # PlainNode永远没有子节点

    @classmethod
    def load(cls, data, **kwargs):
        return super(PlainNode, cls).load(data, **kwargs)


ENABLED_NODES = [
    Base64EncodeNode,
    UrlEncodeNode,
    JSONPNode,
    JSONNode,
    FormNode,
    PlainNode,  # fallback, PlainNode一定匹配成功的
]


def find_proper_node(
        data,
        key=None, parent=None, index_in_parent=None,
        enabled_nodes=ENABLED_NODES,
):
    for node_cls in enabled_nodes:
        node = node_cls.load(
            data,
            key=key, parent=parent,
            index_in_parent=index_in_parent,
        )
        if node is not None:
            return node

    # you should never be here
    raise ValueError("unable to decode data: {}".format(data))


def load(data, recursive=True, **meta):
    """
    解析并加载节点

    已支持格式: Forms/JSON/JSONP
    待添加: XML/BASE64

    Args:
        data (str): 待解析的字符串
        recursive (bool): 是否递归解析,
            若为 False 则只解析最顶层的一个node
        meta (dict[str, int|str]): meta信息, 多数情况下不需要用到

    Returns:
        BaseNode: 每一层解析出来的Node
    """
    root = find_proper_node(data, **meta)
    if recursive:
        root.gen_tree()

    return root


# ---------- 下面是一些方便的辅助函数 -------------
def is_json_or_jsonp(text):
    """
    判断文本是否是json或者jsonp

    如果是json, 返回 "json" (字符串)
    如果是jsonp, 返回 "jsonp"
    如果都不是, 返回 None
    """
    try:
        node = find_proper_node(
            text, enabled_nodes=[JSONPNode, JSONNode]
        )
        if isinstance(node, JSONPNode):
            return "jsonp"
        else:
            return "json"
    except:
        return None


def main():
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
    nested = r"""_callback({})""".format(json.dumps(js))

    print("ori:", nested, "\n\n")

    root_node = load(nested)
    for node in root_node.iter_tree():
        print(" " * node.depth * 4,
              "type:", node.type,
              "| key:", repr(node.key),
              "| abskey:", repr(node.abskey),
              "| data:", repr(node.data),
              "| text:", repr(node.text),
              "| depth:", node.depth,
              "| index_in_parent:", node.index_in_parent
              )

        if node.text == "17":
            node.reload("FFFFFF")

        if node.text == 'b':
            node.data = "IIIIII"
            new_node = node.reload("IIIIII")

        if node.text == 'is':
            node.data = "RRRRRR"
            node.reload("RRRRRR")
        if node.data == 'value-with.a-dot':
            node.data = "EEEEEE"
            new_node = node.reload('''["IIIIII", "a", {"b": "c", "d": "e"}, "this=RRRRRR&a=form"]''')
            print(new_node.key)
            print(new_node.abskey)
            print(new_node.text)

    print("gen:", root_node.text, "\n\n")

    for node in root_node.iter_all_leaves():
        print(" " * node.depth * 4,
              "type:", node.type,
              "| key:", repr(node.key),
              "| abskey:", repr(node.abskey),
              "| data:", repr(node.data),
              "| text:", repr(node.text),
              "| depth:", node.depth)
        node.text = "firesun"

    print("gen:", root_node.text, "\n\n")

    for node in root_node.iter_tree():
        print(" " * node.depth * 4,
              "type:", node.type,
              "| key:", repr(node.key),
              "| abskey:", repr(node.abskey),
              "| data:", repr(node.data),
              "| text:", repr(node.text),
              "| depth:", node.depth)
        node.reload("firesun")
    print("gen:", root_node.text, "\n\n")


if __name__ == '__main__':
    main()
