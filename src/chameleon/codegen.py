try:
    import ast
except ImportError:
    from chameleon import ast24 as ast

import inspect
import textwrap
import types
import copy

try:
    import __builtin__ as builtins
except ImportError:
    import builtins

reverse_builtin_map = {}
for name, value in builtins.__dict__.items():
    try:
        hash(value)
    except TypeError:
        continue

    reverse_builtin_map[value] = name

try:
    basestring
except NameError:
    basestring = str

from .astutil import ASTCodeGenerator
from .astutil import load
from .astutil import store
from .astutil import parse
from .astutil import Builtin
from .astutil import Symbol
from .astutil import node_annotations

from .exc import CompilationError


try:
    NATIVE_NUMBERS = int, float, long, bool
except NameError:
    NATIVE_NUMBERS = int, float, bool


def template(function, mode='exec', **kw):
    def wrapper(*vargs, **kwargs):
        symbols = dict(zip(args, vargs + defaults))
        symbols.update(kwargs)

        class Visitor(ast.NodeVisitor):
            def visit_Name(self, node):
                value = symbols.get(node.id, self)
                if value is not self:
                    if isinstance(value, basestring):
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

        expr = parse(source, mode=mode)
        if not isinstance(function, basestring):
            expr = expr.body[0]

        Visitor().visit(expr)
        return expr.body

    if isinstance(function, basestring):
        source = function
        defaults = args = ()
        return wrapper(**kw)

    source = textwrap.dedent(inspect.getsource(function))
    argspec = inspect.getargspec(function)
    args = argspec[0]
    defaults = argspec[3] or ()
    return wrapper


class TemplateCodeGenerator(ASTCodeGenerator):
    """Extends the standard Python code generator class with handlers
    for the helper node classes:

    - Symbol (an importable value)
    - Static (value that can be made global)
    - Builtin (from the builtins module)
    - Marker (short-hand for a unique static object)

    """

    names = ()

    def __init__(self, tree):
        self.imports = {}
        self.defines = {}
        self.markers = {}

        # Generate code
        super(TemplateCodeGenerator, self).__init__(tree)

    def visit_Module(self, node):
        super(TemplateCodeGenerator, self).visit_Module(node)

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
            name = "_%s" % getattr(value, '__name__', str(value))
            node = load(name)
            self.imports[value] = store(node.id)

        return node

    def visit(self, node):
        annotation = node_annotations.get(node)
        if annotation is None:
            super(TemplateCodeGenerator, self).visit(node)
        else:
            self.visit(annotation)

    def visit_Comment(self, node):
        if node.stmt is None:
            self._new_line()
        else:
            self.visit(node.stmt)

        for line in node.text.replace('\r', '\n').split('\n'):
            self._new_line()
            self._write("%s#%s" % (node.space, line))

    def visit_Builtin(self, node):
        name = load(node.id)
        self.visit(name)

    def visit_Symbol(self, node):
        node = self.require(node.value)
        self.visit(node)

    def visit_Static(self, node):
        if node.name is None:
            name = "_static_%d" % id(node.value)
        else:
            name = node.name

        node = self.define(name, node.value)
        self.visit(node)
