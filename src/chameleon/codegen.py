import ast
import builtins
import textwrap
import types

from .astutil import ASTCodeGenerator
from .astutil import Builtin
from .astutil import Symbol
from .astutil import load
from .astutil import node_annotations
from .astutil import parse
from .astutil import store
from .exc import CompilationError


reverse_builtin_map = {}
for name, value in builtins.__dict__.items():
    try:
        hash(value)
    except TypeError:
        continue

    reverse_builtin_map[value] = name

NATIVE_NUMBERS = int, float, bool


def template(
        source,
        mode='exec',
        is_func=False,
        func_args=(),
        func_defaults=(),
        **kw):
    def wrapper(*vargs, **kwargs):
        symbols = dict(zip(args, vargs + defaults))
        symbols.update(kwargs)

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                self.generic_visit(node)

                name = symbols.get(node.name, self)
                if name is not self:
                    node_annotations[node] = ast.FunctionDef(
                        name=name,
                        args=node.args,
                        body=node.body,
                        decorator_list=getattr(node, "decorator_list", []),
                    )

            def visit_Name(self, node):
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


class TemplateCodeGenerator(ASTCodeGenerator):
    """Extends the standard Python code generator class with handlers
    for the helper node classes:

    - Symbol (an importable value)
    - Static (value that can be made global)
    - Builtin (from the builtins module)
    - Marker (short-hand for a unique static object)

    """

    names = ()

    def __init__(self, tree, source=None):
        self.imports = {}
        self.defines = {}
        self.markers = {}
        self.source = source
        self.tokens = []

        # Generate code
        super().__init__(tree)

    def visit_Module(self, node):
        super().visit_Module(node)

        # Make sure we terminate the line printer
        self.flush()

        # Clear lines array for import visits
        body = self.lines
        self.lines = []

        while self.defines:
            name, node = self.defines.popitem()
            assignment = ast.Assign(targets=[store(name)], value=node)
            self.visit(assignment)

        # Make sure we terminate the line printer
        self.flush()

        # Clear lines array for import visits
        defines = self.lines
        self.lines = []

        while self.imports:
            value, node = self.imports.popitem()

            if isinstance(value, types.ModuleType):
                stmt = ast.Import(
                    names=[ast.alias(name=value.__name__, asname=node.id)])
            elif hasattr(value, '__name__'):
                path = reverse_builtin_map.get(value)
                if path is None:
                    path = value.__module__
                    name = value.__name__
                stmt = ast.ImportFrom(
                    module=path,
                    names=[ast.alias(name=name, asname=node.id)],
                    level=0,
                )
            else:
                raise TypeError(value)

            self.visit(stmt)

        # Clear last import
        self.flush()

        # Stich together lines
        self.lines += defines + body

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
        if value is None:
            return load("None")

        if isinstance(value, NATIVE_NUMBERS):
            return ast.Num(value)

        node = self.imports.get(value)
        if node is None:
            # we come up with a unique symbol based on the class name
            name = "_%s" % getattr(value, '__name__', str(value)).\
                   rsplit('.', 1)[-1]
            node = load(name)
            self.imports[value] = store(node.id)

        return node

    def visit(self, node):
        annotation = node_annotations.get(node)
        if annotation is None:
            super().visit(node)
        else:
            self.visit(annotation)

    def visit_Comment(self, node):
        if node.stmt is None:
            self._new_line()
        else:
            self.visit(node.stmt)

        for line in node.text.replace('\r', '\n').split('\n'):
            self._new_line()
            self._write("{}#{}".format(node.space, line))

    def visit_Builtin(self, node):
        name = load(node.id)
        self.visit(name)

    def visit_Symbol(self, node):
        node = self.require(node.value)
        self.visit(node)

    def visit_Static(self, node):
        if node.name is None:
            name = "_static_%s" % str(id(node.value)).replace('-', '_')
        else:
            name = node.name

        node = self.define(name, node.value)
        self.visit(node)

    def visit_TokenRef(self, node):
        self.tokens.append((node.pos, node.length))
        super().visit(ast.Num(n=node.pos))
