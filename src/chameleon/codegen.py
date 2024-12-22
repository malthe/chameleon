from __future__ import annotations

import builtins
import re
import sys
import textwrap
import types
from ast import AST
from ast import Assign
from ast import Constant
from ast import Expr
from ast import FunctionDef
from ast import Import
from ast import ImportFrom
from ast import Module
from ast import NodeTransformer
from ast import alias
from ast import unparse
from typing import TYPE_CHECKING
from typing import Any

from chameleon.astutil import Builtin
from chameleon.astutil import Symbol
from chameleon.astutil import load
from chameleon.astutil import parse
from chameleon.astutil import store
from chameleon.exc import CompilationError


if TYPE_CHECKING:
    import ast
    from collections.abc import Hashable

    from chameleon.astutil import Comment
    from chameleon.astutil import Static


reverse_builtin_map: dict[type[Any] | Hashable, str] = {}
for name, value in builtins.__dict__.items():
    try:
        hash(value)
    except TypeError:
        continue

    reverse_builtin_map[value] = name


def template(
    source,
    mode='exec',
    is_func: bool = False,
    func_args=(),
    func_defaults=(),
    **kw,
):
    def wrapper(*vargs, **kwargs):
        symbols = dict(zip(args, vargs + defaults))
        symbols.update(kwargs)

        class Transformer(NodeTransformer):
            def visit_FunctionDef(self, node: ast.FunctionDef) -> AST:
                if node.name not in symbols:
                    return self.generic_visit(node)

                name = symbols[node.name]
                assert isinstance(name, str)
                body: list[ast.stmt] = [self.visit(stmt) for stmt in node.body]
                if sys.version_info >= (3, 12):
                    # mypy complains if type_params is missing
                    funcdef = FunctionDef(
                        name=name,
                        args=node.args,
                        body=body,
                        decorator_list=node.decorator_list,
                        returns=node.returns,
                        type_params=node.type_params,
                    )
                else:
                    funcdef = FunctionDef(
                        name=name,
                        args=node.args,
                        body=body,
                        decorator_list=node.decorator_list,
                        returns=node.returns,
                    )
                return funcdef

            def visit_Name(self, node: ast.Name) -> AST:
                value = symbols.get(node.id, self)
                if value is self:
                    if node.id == 'None' or \
                       getattr(builtins, node.id, None) is not None:
                        return Builtin(node.id)
                    return node

                if isinstance(value, type) or value in reverse_builtin_map:
                    name = reverse_builtin_map.get(value)
                    if name is not None:
                        return Builtin(name)
                    return Symbol(value)

                if isinstance(value, str):
                    value = load(value)

                return value  # type: ignore[no-any-return]

        expr = parse(textwrap.dedent(source), mode=mode)

        Transformer().visit(expr)
        return expr.body

    assert isinstance(source, str)
    defaults = func_defaults
    args = func_args
    if is_func:
        return wrapper
    else:
        return wrapper(**kw)


class TemplateCodeGenerator(NodeTransformer):
    """Generate code from AST tree.

    The syntax tree has been extended with internal nodes. We first
    transform the tree to process the internal nodes before generating
    the code string.
    """

    names = ()

    imports: dict[type[Any] | Hashable, ast.Name]

    def __init__(self, tree):
        self.comments = []
        self.defines = {}
        self.imports = {}

        # Run transform.
        tree = self.visit(tree)

        # Generate code.
        code = unparse(tree)

        # Fix-up comments.
        comments = iter(self.comments)
        code = re.sub(
            r'^(\s*)\.\.\.$',
            lambda m: "\n".join(
                (m.group(1) + "#" + line)
                for line in next(comments).replace("\r", "\n").split("\n")
            ),
            code,
            flags=re.MULTILINE
        )

        self.code = code

    def define(self, name, node):
        assert node is not None
        value = self.defines.get(name)

        if value is node:
            pass
        elif value is None:
            self.defines[name] = node
        else:
            raise CompilationError(
                "Duplicate symbol name for define.", name)

        return load(name)

    def require(self, value: type[Any] | Hashable) -> ast.Name:
        node = self.imports.get(value)
        if node is None:
            # we come up with a unique symbol based on the class name
            name = (
                "_%s"
                % getattr(value, '__name__', str(value)).rsplit('.', 1)[-1]
            )
            node = load(name)
            self.imports[value] = store(node.id)

        return node

    def visit_Module(self, module: Module) -> AST:
        assert isinstance(module, Module)
        module = super().generic_visit(module)  # type: ignore[assignment]
        preamble: list[ast.stmt] = []

        for name, node in self.defines.items():
            assignment = Assign(targets=[store(name)], value=node, lineno=-1)
            preamble.append(self.visit(assignment))

        imports: list[ast.stmt] = []
        for value, node in self.imports.items():
            stmt: ast.stmt

            if isinstance(value, types.ModuleType):
                stmt = Import(
                    names=[alias(name=value.__name__, asname=node.id)])
            elif hasattr(value, '__name__'):
                path = reverse_builtin_map.get(value)
                if path is None:
                    path = value.__module__
                    name = value.__name__
                stmt = ImportFrom(
                    module=path,
                    names=[alias(name=name, asname=node.id)],
                    level=0,
                )
            else:
                raise TypeError(value)

            imports.append(stmt)

        return Module(imports + preamble + module.body, [])

    def visit_Comment(self, node: Comment) -> AST:
        self.comments.append(node.text)
        return Expr(Constant(...))

    def visit_Builtin(self, node: Builtin) -> AST:
        name = load(node.id)
        return self.visit(name)  # type: ignore[no-any-return]

    def visit_Symbol(self, node: Symbol) -> AST:
        return self.require(node.value)

    def visit_Static(self, node: Static) -> AST:
        if node.name is None:
            name = "_static_%s" % str(id(node.value)).replace('-', '_')
        else:
            name = node.name
        node = self.define(name, node.value)
        return self.visit(node)  # type: ignore[no-any-return]
