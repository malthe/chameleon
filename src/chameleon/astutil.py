"""Support code for generating code from abstract syntax trees."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import deepcopy
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Hashable
    from collections.abc import Iterator
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
        super().__init__(transform)
        self.reset()

    def reset(self) -> None:
        """Forget the names bound so far."""
        self.scopes: list[set[str]] = [set()]
        # The names of the handlers of the ``try`` being visited that
        # were bound already.
        self.unbound: list[str] = []

    @contextmanager
    def isolated(self) -> Iterator[None]:
        """Forget the names bound inside, which is a function of its
        own that sees the names bound so far."""
        scopes = [set(scope) for scope in self.scopes]
        try:
            yield
        finally:
            self.scopes = scopes

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

    def visit_arguments(self, node: ast.arguments) -> ast.AST:
        # Defaults are evaluated before the parameters are bound: in
        # ``def f(a=a)`` the default is not the parameter.
        self._visit_defaults(node)
        self._visit_parameters(node)
        return node

    def _visit_defaults(self, node: ast.arguments) -> None:
        node.defaults = [self.visit(default) for default in node.defaults]
        node.kw_defaults = [
            default if default is None else self.visit(default)
            for default in node.kw_defaults
        ]

    def _visit_parameters(self, node: ast.arguments) -> None:
        for arg in (
            *node.posonlyargs,
            *node.args,
            node.vararg,
            *node.kwonlyargs,
            node.kwarg,
        ):
            if arg is not None:
                self.visit(arg)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.scopes[-1].add(node.name)
        node.decorator_list = [
            self.visit(decorator) for decorator in node.decorator_list
        ]
        return self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        # Decorators, defaults and annotations are evaluated before the
        # name is bound: in ``async def f(x=f)`` the default is not the
        # function.
        node.decorator_list = [
            self.visit(decorator) for decorator in node.decorator_list
        ]
        return self._visit_function(node)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> ast.AST:
        # The parameters of a function, and the names its body binds
        # with a ``def``, a ``class`` or an import, are its own: after
        # it they are read from the template scope again.
        scope = self.scopes[-1]
        outer = set(scope)
        try:
            node.args = self.visit(node.args)
            if node.returns is not None:
                node.returns = self.visit(node.returns)
            scope.add(node.name)
            return self._visit_fields(
                node, skip=("decorator_list", "args", "returns")
            )
        finally:
            scope.clear()
            scope.update(outer)
            scope.add(node.name)

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
        name = node.name
        if name is None:
            return self._visit_fields(node, skip=("type", ))
        if name not in scope:
            scope.add(name)
            try:
                return self._visit_fields(node, skip=("type", ))
            finally:
                scope.discard(name)

        # The name is bound already, by a ``def`` for example, and is
        # read as a local whether the handler runs or not: see
        # ``visit_Try``.
        if name not in self.unbound:
            self.unbound.append(name)
        return self._visit_fields(node, skip=("type", ))

    def visit_Try(self, node: ast.Try | ast.TryStar) -> ast.AST:
        # A handler unbinds its name when it is done. For a name that
        # was bound already, and stays a local, the value in the
        # template scope is bound in its place if there is one: the
        # name reads as it does for a handler that binds a name which
        # was not bound.
        outer, self.unbound = self.unbound, []
        try:
            node.body = self._visit_body(node.body)
            node.handlers = [
                self.visit(handler) for handler in node.handlers
            ]
            names = self.unbound
        finally:
            self.unbound = outer
        node.orelse = self._visit_body(node.orelse)
        finalbody = self._visit_body(node.finalbody)

        rebind: list[ast.stmt] = []
        for name in names:
            stmt = ast.parse(
                "try:\n"
                "    NAME\n"
                "except NameError:\n"
                "    try:\n"
                "        NAME = None\n"
                "    except NameError:\n"
                "        pass\n".replace("NAME", name)
            ).body[0]
            assert isinstance(stmt, ast.Try)
            fallback = stmt.handlers[0].body[0]
            assert isinstance(fallback, ast.Try)
            assign = fallback.body[0]
            assert isinstance(assign, ast.Assign)
            value = self.apply_transform(load(name))
            assert isinstance(value, ast.expr)
            assign.value = value
            rebind.append(stmt)
        node.finalbody = rebind + finalbody
        return node

    visit_TryStar = visit_Try

    def _visit_body(self, body: list[ast.stmt]) -> list[ast.stmt]:
        stmts: list[ast.stmt] = []
        for stmt in body:
            visited = self.visit(stmt)
            if isinstance(visited, list):
                stmts.extend(visited)
            elif visited is not None:
                stmts.append(visited)
        return stmts

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
        # Defaults belong to the scope the lambda is written in.
        self._visit_defaults(node.args)
        self.scopes.append(set())
        try:
            self._visit_parameters(node.args)
            node.body = self.visit(node.body)
            return node
        finally:
            self.scopes.pop()


class ItemLookupOnAttributeErrorVisitor(NodeTransformerBase):
    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        transformed = self.apply_transform(node)
        return self.generic_visit(transformed)
