from __future__ import annotations

import builtins
import re
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
from ast import NodeVisitor
from ast import Num
from ast import alias
from ast import unparse

from chameleon.astutil import Builtin
from chameleon.astutil import Symbol
from chameleon.astutil import load
from chameleon.astutil import node_annotations
from chameleon.astutil import parse
from chameleon.astutil import store
from chameleon.exc import CompilationError


reverse_builtin_map = {}
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

        class Visitor(NodeVisitor):
            def visit_FunctionDef(self, node) -> None:
                self.generic_visit(node)

                name = symbols.get(node.name, self)
                if name is not self:
                    node_annotations[node] = FunctionDef(
                        name=name,
                        args=node.args,
                        body=node.body,
                        decorator_list=getattr(node, "decorator_list", []),
                        lineno=None,
                    )

            def visit_Name(self, node) -> None:
                value = symbols.get(node.id, self)
                if value is not self:
                    if isinstance(value, str):
                        value = load(value)
                    if isinstance(value, type) or value in reverse_builtin_map:
                        name = reverse_builtin_map.get(value)
                        if name is not None:
                            value = Builtin(name)
                        else:
                            value = Symbol(value)

                    assert node not in node_annotations
                    assert hasattr(value, '_fields')
                    node_annotations[node] = value

        expr = parse(textwrap.dedent(source), mode=mode)

        Visitor().visit(expr)
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

    def __init__(self, tree):
        self.comments = []
        self.defines = {}
        self.imports = {}
        self.tokens = []

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

    def require(self, value):
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

    def visit(self, node) -> AST:
        annotation = node_annotations.get(node)
        if annotation is None:
            return super().visit(node)
        return self.visit(annotation)

    def visit_Module(self, module) -> AST:
        assert isinstance(module, Module)
        module = super().generic_visit(module)
        preamble: list[AST] = []

        for name, node in self.defines.items():
            assignment = Assign(targets=[store(name)], value=node, lineno=None)
            preamble.append(assignment)

        for value, node in self.imports.items():
            stmt: AST

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

            preamble.append(stmt)

        preamble = [self.visit(stmt) for stmt in preamble]
        return Module(preamble + module.body, ())

    def visit_Comment(self, node) -> AST:
        self.comments.append(node.text)
        return Expr(Constant(...))

    def visit_Builtin(self, node) -> AST:
        name = load(node.id)
        return self.visit(name)

    def visit_Symbol(self, node) -> AST:
        return self.require(node.value)

    def visit_Static(self, node) -> AST:
        if node.name is None:
            name = "_static_%s" % str(id(node.value)).replace('-', '_')
        else:
            name = node.name
        node = self.define(name, node.value)
        return self.visit(node)

    def visit_TokenRef(self, node) -> AST:
        self.tokens.append((node.pos, node.length))
        return self.visit(Num(n=node.pos))
