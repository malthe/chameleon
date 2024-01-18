"""Support code for generating code from abstract syntax trees."""

from __future__ import annotations

import ast
from copy import deepcopy
from typing import TYPE_CHECKING
from typing import ClassVar


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Union
    _NodeTransform = Callable[[ast.AST], Union[ast.AST, None]]


__docformat__ = 'restructuredtext en'


def parse(source, mode='eval'):
    return compile(source, '', mode, ast.PyCF_ONLY_AST)


def load(name):
    return ast.Name(id=name, ctx=ast.Load())


def store(name):
    return ast.Name(id=name, ctx=ast.Store())


def param(name):
    return ast.Name(id=name, ctx=ast.Param())


def subscript(name, value, ctx):
    return ast.Subscript(
        value=value,
        slice=ast.Index(value=ast.Str(s=name)),
        ctx=ctx,
    )


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


class NodeTransformerBase(ast.NodeTransformer):
    def __init__(self, transform: _NodeTransform):
        self.transform = transform

    def apply_transform(self, node: ast.AST) -> ast.AST:
        result = self.transform(node)
        if result is not None:
            return result
        return node


class NameLookupRewriteVisitor(NodeTransformerBase):
    def __init__(self, transform: _NodeTransform):
        self.scopes: list[set[str]] = [set()]
        super().__init__(transform)

    def __call__(self, node) -> ast.AST:
        clone = deepcopy(node)
        return self.visit(clone)

    def visit_arg(self, node) -> ast.AST:
        scope = self.scopes[-1]
        scope.add(node.arg)
        return node

    def visit_Name(self, node) -> ast.AST:
        scope = self.scopes[-1]
        if isinstance(node.ctx, ast.Param):
            scope.add(node.id)
            return node
        if node.id not in scope:
            node = self.apply_transform(node)
        return node

    def visit_FunctionDef(self, node) -> ast.AST:
        self.scopes[-1].add(node.name)
        return super().generic_visit(node)

    def visit_alias(self, node) -> ast.AST:
        name = node.asname if node.asname is not None else node.name
        self.scopes[-1].add(name)
        return super().generic_visit(node)

    def visit_Lambda(self, node) -> ast.AST:
        self.scopes.append(set())
        try:
            return super().generic_visit(node)
        finally:
            self.scopes.pop()


class ItemLookupOnAttributeErrorVisitor(NodeTransformerBase):
    def visit_Attribute(self, node) -> ast.AST:
        node = self.apply_transform(node)
        return self.generic_visit(node)
