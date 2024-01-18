"""Support code for generating code from abstract syntax trees."""

from __future__ import annotations

import ast
import collections
import weakref
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import MutableMapping
    from typing import TypeVar
    from typing_extensions import TypeAlias

    _F = TypeVar('_F', bound=Callable[..., Any])
    _AnyNode: TypeAlias = 'Node | ast.AST'
    _Position: TypeAlias = tuple[int, int]
    _LineInfo: TypeAlias = 'list[tuple[int, _Position | None]]'

AST_NONE = ast.Name(id='None', ctx=ast.Load())

node_annotations: MutableMapping[_AnyNode, _AnyNode]
node_annotations = weakref.WeakKeyDictionary()

__docformat__ = 'restructuredtext en'


def annotated(value):
    node = load("annotation")
    node_annotations[node] = value
    return node


def parse(source, mode='eval'):
    return compile(source, '', mode, ast.PyCF_ONLY_AST)


def load(name):
    return ast.Name(id=name, ctx=ast.Load())


def store(name):
    return ast.Name(id=name, ctx=ast.Store())


def param(name):
    return ast.Name(id=name, ctx=ast.Param())


def delete(name):
    return ast.Name(id=name, ctx=ast.Del())


def subscript(name, value, ctx):
    return ast.Subscript(
        value=value,
        slice=ast.Index(value=ast.Str(s=name)),
        ctx=ctx,
    )


def walk_names(target, mode):
    for node in ast.walk(target):
        if isinstance(node, ast.Name) and \
                isinstance(node.ctx, mode):
            yield node.id


def iter_fields(node):
    """
    Yield a tuple of ``(fieldname, value)`` for each field in ``node._fields``
    that is present on *node*.
    """
    for field in node._fields:
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass


def iter_child_nodes(node):
    """
    Yield all direct child nodes of *node*, that is, all fields that are nodes
    and all items of fields that are lists of nodes.
    """
    for name, field in iter_fields(node):
        if isinstance(field, Node):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, Node):
                    yield item


def walk(node):
    """
    Recursively yield all descendant nodes in the tree starting at *node*
    (including *node* itself), in no specified order.  This is useful if you
    only want to modify nodes in place and don't care about the context.
    """
    todo = collections.deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


def copy(source, target) -> None:
    target.__class__ = source.__class__
    target.__dict__ = source.__dict__


def marker(name):
    return ast.Str(s="__%s" % name)


class Node(ast.AST):
    """AST baseclass that gives us a convenient initialization
    method. We explicitly declare and use the ``_fields`` attribute."""

    _fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, *args, **kwargs) -> None:
        assert isinstance(self._fields, tuple)
        self.__dict__.update(kwargs)
        for name, value in zip(self._fields, args):
            setattr(self, name, value)

    def __repr__(self) -> str:
        """Poor man's single-line pretty printer."""

        name = type(self).__name__
        return '<{}{} at {:x}>'.format(
            name,
            "".join(
                " {}={!r}".format(name, getattr(self, name, "\"?\""))
                for name in self._fields
            ),
            id(self),
        )

    def extract(self, condition):
        result = []
        for node in walk(self):
            if condition(node):
                result.append(node)

        return result


class Builtin(Node):
    """Represents a Python builtin.

    Used when a builtin is used internally by the compiler, to avoid
    clashing with a user assignment (e.g. ``help`` is a builtin, but
    also commonly assigned in templates).
    """

    _fields = "id", "ctx"

    ctx = ast.Load()


class Symbol(Node):
    """Represents an importable symbol."""

    _fields = "value",


class Static(Node):
    """Represents a static value."""

    _fields = "value", "name"

    name = None


class Comment(Node):
    _fields = "text",


class TokenRef(Node):
    """Represents a source-code token reference."""

    _fields = "token",


class AnnotationAwareVisitor(ast.NodeVisitor):
    def visit(self, node) -> None:
        annotation = node_annotations.get(node)
        if annotation is not None:
            assert hasattr(annotation, '_fields')
        super().visit(node)

    def apply_transform(self, node):
        if node not in node_annotations:
            result = self.transform(node)
            if result is not None and result is not node:
                node_annotations[node] = result


class NameLookupRewriteVisitor(AnnotationAwareVisitor):
    def __init__(self, transform):
        self.transform = transform
        self.transformed = set()
        self.scopes = [set()]

    def __call__(self, node):
        self.visit(node)

    def visit_arg(self, node) -> None:
        scope = self.scopes[-1]
        scope.add(node.arg)

    def visit_Name(self, node) -> None:
        scope = self.scopes[-1]
        if isinstance(node.ctx, ast.Param):
            scope.add(node.id)
        elif node.id not in scope:
            self.transformed.add(node.id)
            self.apply_transform(node)

    def visit_FunctionDef(self, node) -> None:
        self.scopes[-1].add(node.name)

    def visit_alias(self, node) -> None:
        name = node.asname if node.asname is not None else node.name
        self.scopes[-1].add(name)

    def visit_Lambda(self, node) -> None:
        self.scopes.append(set())
        try:
            self.visit(node.args)
            self.visit(node.body)
        finally:
            self.scopes.pop()


class ItemLookupOnAttributeErrorVisitor(AnnotationAwareVisitor):
    def __init__(self, transform):
        self.transform = transform

    def visit_Attribute(self, node) -> None:
        self.generic_visit(node)
        self.apply_transform(node)
