"""Support code for generating code from abstract syntax trees."""

from __future__ import annotations

import ast
from copy import deepcopy
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Hashable
    from typing import Optional

    from chameleon.tokenize import Token

    _NodeTransform = Callable[[ast.AST], Optional[ast.AST]]


__docformat__ = 'restructuredtext en'


def parse(source, mode: str = 'eval') -> ast.AST:
    return compile(source, '', mode, ast.PyCF_ONLY_AST)


def load(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Load())


def store(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Store())


def param(name: str) -> ast.Name:
    return ast.Name(id=name, ctx=ast.Param())


def subscript(
    name: str,
    value: ast.expr,
    ctx: ast.expr_context
) -> ast.Subscript:
    return ast.Subscript(
        value=value,
        slice=ast.Constant(name),
        ctx=ctx,
    )


class Node(ast.AST):
    """AST baseclass that gives us a convenient initialization
    method. We explicitly declare and use the ``_fields`` attribute."""

    _fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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

    id: str
    ctx = ast.Load()


class Symbol(Node):
    """Represents an importable symbol."""

    _fields = "value",

    # Apart from a few builtins this should be type[Any]
    value: type[Any] | Hashable


class Static(Node):
    """Represents a static value."""

    _fields = "value", "name"

    value: ast.expr
    name: str | None = None


class Comment(Node):
    _fields = "text",

    text: str


class TokenRef(Node):
    """Represents a source-code token reference."""

    _fields = "token",

    token: Token


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

    def __call__(self, node: ast.AST) -> ast.AST:
        clone = deepcopy(node)
        return self.visit(clone)  # type: ignore[no-any-return]

    def visit_arg(self, node: ast.arg) -> ast.AST:
        scope = self.scopes[-1]
        scope.add(node.arg)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        scope = self.scopes[-1]
        if isinstance(node.ctx, ast.Param):
            scope.add(node.id)
            return node
        if node.id not in scope:
            return self.apply_transform(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.scopes[-1].add(node.name)
        return super().generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        # Decorators, defaults and annotations are evaluated before the
        # name is bound: in ``async def f(x=f)`` the default is not the
        # function.
        node.decorator_list = [
            self.visit(decorator) for decorator in node.decorator_list
        ]
        node.args = self.visit(node.args)
        if node.returns is not None:
            node.returns = self.visit(node.returns)
        self.scopes[-1].add(node.name)
        return self._visit_fields(
            node, skip=("decorator_list", "args", "returns")
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        # Decorators, bases and keywords are evaluated before the name
        # is bound: in ``class Base(Base)`` the base is not the class.
        header = ("decorator_list", "bases", "keywords")
        for field in header:
            setattr(node, field, [
                self.visit(child) for child in getattr(node, field)
            ])
        self.scopes[-1].add(node.name)
        return self._visit_fields(node, skip=header)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        # The type is evaluated before the name is bound. The name is
        # bound for the handler only: Python unbinds it when the
        # handler is done.
        if node.type is not None:
            node.type = self.visit(node.type)
        scope = self.scopes[-1]
        if node.name is None or node.name in scope:
            return self._visit_fields(node, skip=("type", ))
        scope.add(node.name)
        try:
            return self._visit_fields(node, skip=("type", ))
        finally:
            scope.discard(node.name)

    def _visit_fields(self, node: ast.AST, skip: tuple[str, ...]) -> ast.AST:
        """Visit the fields of ``node`` that are not in ``skip``."""
        for field, value in ast.iter_fields(node):
            if field in skip:
                continue
            if isinstance(value, list):
                children: list[ast.AST] = []
                for child in value:
                    if not isinstance(child, ast.AST):
                        children.append(child)
                        continue
                    visited = self.visit(child)
                    if isinstance(visited, list):
                        children.extend(visited)
                    elif visited is not None:
                        children.append(visited)
                setattr(node, field, children)
            elif isinstance(value, ast.AST):
                setattr(node, field, self.visit(value))
        return node

    def visit_match_case(self, node: ast.match_case) -> ast.AST:
        # The names a pattern captures can only be plain names. They
        # are for the guard, and assigned like any other name first
        # thing in the body.
        scope = self.scopes[-1]
        names: list[str] = []
        for pattern in ast.walk(node.pattern):
            if isinstance(pattern, (ast.MatchAs, ast.MatchStar)):
                name = pattern.name
            elif isinstance(pattern, ast.MatchMapping):
                name = pattern.rest
            else:
                continue
            if name is not None and name not in scope and name not in names:
                names.append(name)

        node.pattern = self.visit(node.pattern)
        if node.guard is not None:
            scope.update(names)
            try:
                node.guard = self.visit(node.guard)
            finally:
                scope.difference_update(names)

        body: list[ast.stmt] = []
        for name in names:
            target = self.visit(ast.Name(id=name, ctx=ast.Store()))
            if not isinstance(target, ast.Name):
                body.append(ast.Assign(
                    targets=[target],
                    value=ast.Name(id=name, ctx=ast.Load()),
                ))
        for stmt in node.body:
            visited = self.visit(stmt)
            if isinstance(visited, list):
                body.extend(visited)
            else:
                body.append(visited)
        node.body = body
        return node

    def visit_alias(self, node: ast.alias) -> ast.AST:
        name = node.asname if node.asname is not None else node.name
        self.scopes[-1].add(name)
        return super().generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        self.scopes.append(set())
        try:
            return super().generic_visit(node)
        finally:
            self.scopes.pop()


class ItemLookupOnAttributeErrorVisitor(NodeTransformerBase):
    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        transformed = self.apply_transform(node)
        return self.generic_visit(transformed)
