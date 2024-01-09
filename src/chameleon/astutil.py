#
# Copyright (C) 2008-2009 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""Support classes for generating code from abstract syntax trees."""

from __future__ import annotations

import ast
import collections
import logging
import weakref
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import cast


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

try:
    node_annotations[ast.Name()] = None  # type: ignore[assignment]
except TypeError:
    logging.debug(
        "Unable to create weak references to AST nodes. "
        "A lock will be used around compilation loop."
    )

    node_annotations = {}

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


def swap(body, replacement, name) -> None:
    root = ast.Expression(body=body)
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == name
        ):
            assert hasattr(replacement, '_fields')
            node_annotations.setdefault(node, replacement)


def marker(name):
    return ast.Str(s="__%s" % name)


class Node:
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
    _fields = "text", "space", "stmt"

    stmt = None
    space = ""


class TokenRef(Node):
    """Represents a source-code token reference."""

    _fields = "pos", "length"


class ASTCodeGenerator:
    """General purpose base class for AST transformations.

    Every visitor method can be overridden to return an AST node that has been
    altered or replaced in some way.
    """

    def __init__(self, tree):
        self.lines_info = []
        self.line_info = []
        self.lines = []
        self.line = ""
        self.last = None
        self.indent = 0
        self.blame_stack = []
        self.visit(tree)

        if self.line.strip():
            self._new_line()

        self.line = None
        self.line_info = None

        # strip trivial lines
        self.code = "\n".join(
            line.strip() and line or "" for line in self.lines
        )

    def _change_indent(self, delta) -> None:
        self.indent += delta

    def _new_line(self) -> None:
        if self.line is not None:
            self.lines.append(self.line)
            self.lines_info.append(self.line_info)
        self.line = ' ' * 4 * self.indent
        if len(self.blame_stack) == 0:
            self.line_info = []
            self.last = None
        else:
            self.line_info = [
                (
                    0,
                    self.blame_stack[-1],
                )
            ]
            self.last = self.blame_stack[-1]

    def _write(self, s) -> None:
        if len(s) == 0:
            return
        if len(self.blame_stack) == 0:
            if self.last is not None:
                self.last = None
                self.line_info.append((len(self.line), self.last))
        else:
            if self.last != self.blame_stack[-1]:
                self.last = self.blame_stack[-1]
                self.line_info.append((len(self.line), self.last))
        self.line += s

    def flush(self) -> None:
        if self.line:
            self._new_line()

    def visit(self, node):
        if node is None:
            return None
        if isinstance(node, tuple):
            return tuple([self.visit(n) for n in node])
        try:
            self.blame_stack.append(
                (
                    node.lineno,
                    node.col_offset,
                )
            )
            info = True
        except AttributeError:
            info = False
        visitor = getattr(self, 'visit_%s' % node.__class__.__name__, None)
        if visitor is None:
            raise Exception(
                'No handler for ``{}`` ({}).'.format(
                    node.__class__.__name__, repr(node)
                )
            )
        ret = visitor(node)
        if info:
            self.blame_stack.pop()
        return ret

    def visit_Module(self, node) -> None:
        for n in node.body:
            self.visit(n)

    visit_Interactive = visit_Module
    visit_Suite = visit_Module

    def visit_Expression(self, node):
        return self.visit(node.body)

    # arguments = (expr* args, identifier? vararg,
    #              identifier? kwarg, expr* defaults)
    def visit_arguments(self, node) -> None:
        first = True
        no_default_count = len(node.args) - len(node.defaults)
        for i, arg in enumerate(node.args):
            if not first:
                self._write(', ')
            else:
                first = False
            self.visit(arg)
            if i >= no_default_count:
                self._write('=')
                self.visit(node.defaults[i - no_default_count])
        if getattr(node, 'vararg', None):
            if not first:
                self._write(', ')
            else:
                first = False
            self._write('*' + node.vararg)
        if getattr(node, 'kwarg', None):
            if not first:
                self._write(', ')
            else:
                first = False
            self._write('**' + node.kwarg)

    def visit_arg(self, node) -> None:
        self._write(node.arg)

    # FunctionDef(identifier name, arguments args,
    #                           stmt* body, expr* decorators)
    def visit_FunctionDef(self, node) -> None:
        self._new_line()
        for decorator in getattr(node, 'decorator_list', ()):
            self._new_line()
            self._write('@')
            self.visit(decorator)
        self._new_line()
        self._write('def ' + node.name + '(')
        self.visit(node.args)
        self._write('):')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)

    # ClassDef(identifier name, expr* bases, stmt* body)
    def visit_ClassDef(self, node) -> None:
        self._new_line()
        self._write('class ' + node.name)
        if node.bases:
            self._write('(')
            self.visit(node.bases[0])
            for base in node.bases[1:]:
                self._write(', ')
                self.visit(base)
            self._write(')')
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)

    # Return(expr? value)
    def visit_Return(self, node) -> None:
        self._new_line()
        self._write('return')
        if getattr(node, 'value', None):
            self._write(' ')
            self.visit(node.value)

    # Delete(expr* targets)
    def visit_Delete(self, node) -> None:
        self._new_line()
        self._write('del ')
        self.visit(node.targets[0])
        for target in node.targets[1:]:
            self._write(', ')
            self.visit(target)

    # Assign(expr* targets, expr value)
    def visit_Assign(self, node) -> None:
        self._new_line()
        for target in node.targets:
            self.visit(target)
            self._write(' = ')
        self.visit(node.value)

    # AugAssign(expr target, operator op, expr value)
    def visit_AugAssign(self, node) -> None:
        self._new_line()
        self.visit(node.target)
        self._write(' ' + self.binary_operators[node.op.__class__] + '= ')
        self.visit(node.value)

    # JoinedStr(expr* values)
    def visit_JoinedStr(self, node) -> None:
        if node.values:
            self._write('"".join((')
            for value in node.values:
                self.visit(value)
                self._write(',')
            self._write('))')
        else:
            self._write('""')

    # FormattedValue(expr value)
    def visit_FormattedValue(self, node) -> None:
        if node.conversion == ord('r'):
            self._write('repr')
        elif node.conversion == ord('a'):
            self._write('ascii')
        else:
            self._write('str')
        self._write('(')
        self.visit(node.value)
        if node.format_spec is not None:
            self._write('.__format__(')
            self.visit(node.format_spec)
            self._write(')')
        self._write(')')

    # Print(expr? dest, expr* values, bool nl)
    def visit_Print(self, node) -> None:
        self._new_line()
        self._write('print')
        if getattr(node, 'dest', None):
            self._write(' >> ')
            self.visit(node.dest)
            if getattr(node, 'values', None):
                self._write(', ')
        else:
            self._write(' ')
        if getattr(node, 'values', None):
            self.visit(node.values[0])
            for value in node.values[1:]:
                self._write(', ')
                self.visit(value)
        if not node.nl:
            self._write(',')

    # For(expr target, expr iter, stmt* body, stmt* orelse)
    def visit_For(self, node) -> None:
        self._new_line()
        self._write('for ')
        self.visit(node.target)
        self._write(' in ')
        self.visit(node.iter)
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)
        if getattr(node, 'orelse', None):
            self._new_line()
            self._write('else:')
            self._change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self._change_indent(-1)

    # While(expr test, stmt* body, stmt* orelse)
    def visit_While(self, node) -> None:
        self._new_line()
        self._write('while ')
        self.visit(node.test)
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)
        if getattr(node, 'orelse', None):
            self._new_line()
            self._write('else:')
            self._change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self._change_indent(-1)

    # If(expr test, stmt* body, stmt* orelse)
    def visit_If(self, node) -> None:
        self._new_line()
        self._write('if ')
        self.visit(node.test)
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)
        if getattr(node, 'orelse', None):
            self._new_line()
            self._write('else:')
            self._change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self._change_indent(-1)

    # With(expr context_expr, expr? optional_vars, stmt* body)
    def visit_With(self, node) -> None:
        self._new_line()
        self._write('with ')
        self.visit(node.context_expr)
        if getattr(node, 'optional_vars', None):
            self._write(' as ')
            self.visit(node.optional_vars)
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)

    # Raise(expr? type, expr? inst, expr? tback)
    def visit_Raise(self, node):
        self._new_line()
        self._write('raise')
        if not getattr(node, "type", None):
            exc = getattr(node, "exc", None)
            if exc is None:
                return
            self._write(' ')
            return self.visit(exc)
        self._write(' ')
        self.visit(node.type)
        if not node.inst:
            return
        self._write(', ')
        self.visit(node.inst)
        if not node.tback:
            return
        self._write(', ')
        self.visit(node.tback)

    # Try(stmt* body, excepthandler* handlers, stmt* orelse, stmt* finalbody)
    def visit_Try(self, node) -> None:
        self._new_line()
        self._write('try:')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)
        if getattr(node, 'handlers', None):
            for handler in node.handlers:
                self.visit(handler)
        self._new_line()

        if getattr(node, 'orelse', None):
            self._write('else:')
            self._change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self._change_indent(-1)

        if getattr(node, 'finalbody', None):
            self._new_line()
            self._write('finally:')
            self._change_indent(1)
            for statement in node.finalbody:
                self.visit(statement)
            self._change_indent(-1)

    # TryExcept(stmt* body, excepthandler* handlers, stmt* orelse)
    def visit_TryExcept(self, node) -> None:
        self._new_line()
        self._write('try:')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)
        if getattr(node, 'handlers', None):
            for handler in node.handlers:
                self.visit(handler)
        self._new_line()
        if getattr(node, 'orelse', None):
            self._write('else:')
            self._change_indent(1)
            for statement in node.orelse:
                self.visit(statement)
            self._change_indent(-1)

    # excepthandler = (expr? type, expr? name, stmt* body)
    def visit_ExceptHandler(self, node) -> None:
        self._new_line()
        self._write('except')
        if getattr(node, 'type', None):
            self._write(' ')
            self.visit(node.type)
        if getattr(node, 'name', None):
            self._write(' as ')
            self.visit(node.name)
        self._write(':')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)

    visit_excepthandler = visit_ExceptHandler

    # TryFinally(stmt* body, stmt* finalbody)
    def visit_TryFinally(self, node) -> None:
        self._new_line()
        self._write('try:')
        self._change_indent(1)
        for statement in node.body:
            self.visit(statement)
        self._change_indent(-1)

        if getattr(node, 'finalbody', None):
            self._new_line()
            self._write('finally:')
            self._change_indent(1)
            for statement in node.finalbody:
                self.visit(statement)
            self._change_indent(-1)

    # Assert(expr test, expr? msg)
    def visit_Assert(self, node) -> None:
        self._new_line()
        self._write('assert ')
        self.visit(node.test)
        if getattr(node, 'msg', None):
            self._write(', ')
            self.visit(node.msg)

    def visit_alias(self, node) -> None:
        self._write(node.name)
        if getattr(node, 'asname', None):
            self._write(' as ')
            self._write(node.asname)

    # Import(alias* names)
    def visit_Import(self, node) -> None:
        self._new_line()
        self._write('import ')
        self.visit(node.names[0])
        for name in node.names[1:]:
            self._write(', ')
            self.visit(name)

    # ImportFrom(identifier module, alias* names, int? level)
    def visit_ImportFrom(self, node) -> None:
        self._new_line()
        self._write('from ')
        if node.level:
            self._write('.' * node.level)
        self._write(node.module)
        self._write(' import ')
        self.visit(node.names[0])
        for name in node.names[1:]:
            self._write(', ')
            self.visit(name)

    # Exec(expr body, expr? globals, expr? locals)
    def visit_Exec(self, node) -> None:
        self._new_line()
        self._write('exec ')
        self.visit(node.body)
        if not node.globals:
            return
        self._write(', ')
        self.visit(node.globals)
        if not node.locals:
            return
        self._write(', ')
        self.visit(node.locals)

    # Global(identifier* names)
    def visit_Global(self, node) -> None:
        self._new_line()
        self._write('global ')
        self.visit(node.names[0])
        for name in node.names[1:]:
            self._write(', ')
            self.visit(name)

    # Expr(expr value)
    def visit_Expr(self, node) -> None:
        self._new_line()
        self.visit(node.value)

    # Pass
    def visit_Pass(self, node) -> None:
        self._new_line()
        self._write('pass')

    # Break
    def visit_Break(self, node) -> None:
        self._new_line()
        self._write('break')

    # Continue
    def visit_Continue(self, node) -> None:
        self._new_line()
        self._write('continue')

    # EXPRESSIONS
    def with_parens(f: _F) -> _F:  # type: ignore[misc]
        def _f(self, node) -> None:
            self._write('(')
            f(self, node)
            self._write(')')

        return cast('_F', _f)

    bool_operators = {ast.And: 'and', ast.Or: 'or'}

    # BoolOp(boolop op, expr* values)
    @with_parens
    def visit_BoolOp(self, node) -> None:
        joiner = ' ' + self.bool_operators[node.op.__class__] + ' '
        self.visit(node.values[0])
        for value in node.values[1:]:
            self._write(joiner)
            self.visit(value)

    binary_operators = {
        ast.Add: '+',
        ast.Sub: '-',
        ast.Mult: '*',
        ast.Div: '/',
        ast.Mod: '%',
        ast.Pow: '**',
        ast.LShift: '<<',
        ast.RShift: '>>',
        ast.BitOr: '|',
        ast.BitXor: '^',
        ast.BitAnd: '&',
        ast.FloorDiv: '//',
    }

    # BinOp(expr left, operator op, expr right)
    @with_parens
    def visit_BinOp(self, node) -> None:
        self.visit(node.left)
        self._write(' ' + self.binary_operators[node.op.__class__] + ' ')
        self.visit(node.right)

    unary_operators = {
        ast.Invert: '~',
        ast.Not: 'not',
        ast.UAdd: '+',
        ast.USub: '-',
    }

    # UnaryOp(unaryop op, expr operand)
    def visit_UnaryOp(self, node) -> None:
        self._write(self.unary_operators[node.op.__class__] + ' ')
        self.visit(node.operand)

    # Lambda(arguments args, expr body)
    @with_parens
    def visit_Lambda(self, node) -> None:
        self._write('lambda ')
        self.visit(node.args)
        self._write(': ')
        self.visit(node.body)

    # IfExp(expr test, expr body, expr orelse)
    @with_parens
    def visit_IfExp(self, node) -> None:
        self.visit(node.body)
        self._write(' if ')
        self.visit(node.test)
        self._write(' else ')
        self.visit(node.orelse)

    # Dict(expr* keys, expr* values)
    def visit_Dict(self, node) -> None:
        self._write('{')
        for key, value in zip(node.keys, node.values):
            self.visit(key)
            self._write(': ')
            self.visit(value)
            self._write(', ')
        self._write('}')

    def visit_Set(self, node) -> None:
        self._write('{')
        elts = list(node.elts)
        last = elts.pop()
        for elt in elts:
            self.visit(elt)
            self._write(', ')
        self.visit(last)
        self._write('}')

    # DictComp(expr key, expr value, comprehension* generators)
    def visit_DictComp(self, node) -> None:
        self._write('{')
        self.visit(node.key)
        self._write(': ')
        self.visit(node.value)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self._write(' for ')
            self.visit(generator.target)
            self._write(' in ')
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self._write(' if ')
                self.visit(ifexpr)
        self._write('}')

    # ListComp(expr elt, comprehension* generators)
    def visit_ListComp(self, node) -> None:
        self._write('[')
        self.visit(node.elt)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self._write(' for ')
            self.visit(generator.target)
            self._write(' in ')
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self._write(' if ')
                self.visit(ifexpr)
        self._write(']')

    # GeneratorExp(expr elt, comprehension* generators)
    def visit_GeneratorExp(self, node) -> None:
        self._write('(')
        self.visit(node.elt)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self._write(' for ')
            self.visit(generator.target)
            self._write(' in ')
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self._write(' if ')
                self.visit(ifexpr)
        self._write(')')

    # SetComp(expr elt, comprehension* generators)
    def visit_SetComp(self, node) -> None:
        self._write('{')
        self.visit(node.elt)
        for generator in node.generators:
            # comprehension = (expr target, expr iter, expr* ifs)
            self._write(' for ')
            self.visit(generator.target)
            self._write(' in ')
            self.visit(generator.iter)
            for ifexpr in generator.ifs:
                self._write(' if ')
                self.visit(ifexpr)
                self._write('}')

    # Yield(expr? value)
    def visit_Yield(self, node) -> None:
        self._write('yield')
        if getattr(node, 'value', None):
            self._write(' ')
            self.visit(node.value)

    comparison_operators = {
        ast.Eq: '==',
        ast.NotEq: '!=',
        ast.Lt: '<',
        ast.LtE: '<=',
        ast.Gt: '>',
        ast.GtE: '>=',
        ast.Is: 'is',
        ast.IsNot: 'is not',
        ast.In: 'in',
        ast.NotIn: 'not in',
    }

    # Compare(expr left, cmpop* ops, expr* comparators)
    @with_parens
    def visit_Compare(self, node) -> None:
        self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            self._write(' ' + self.comparison_operators[op.__class__] + ' ')
            self.visit(comparator)

    # Call(expr func, expr* args, keyword* keywords,
    #                         expr? starargs, expr? kwargs)
    def visit_Call(self, node) -> None:
        self.visit(node.func)
        self._write('(')
        first = True
        for arg in node.args:
            if not first:
                self._write(', ')
            first = False
            self.visit(arg)

        for keyword in node.keywords:
            if not first:
                self._write(', ')
            first = False
            # keyword = (identifier arg, expr value)
            if keyword.arg is not None:
                self._write(keyword.arg)
                self._write('=')
            else:
                self._write('**')
            self.visit(keyword.value)

        self._write(')')

    # Repr(expr value)
    def visit_Repr(self, node) -> None:
        self._write('`')
        self.visit(node.value)
        self._write('`')

    # Constant(object value)
    def visit_Constant(self, node) -> None:
        if node.value is Ellipsis:
            self._write('...')
        else:
            self._write(repr(node.value))

    # Num(object n)
    def visit_Num(self, node) -> None:
        self._write(repr(node.n))

    # Str(string s)
    def visit_Str(self, node) -> None:
        self._write(repr(node.s))

    def visit_Ellipsis(self, node) -> None:
        self._write('...')

    # Attribute(expr value, identifier attr, expr_context ctx)
    def visit_Attribute(self, node) -> None:
        self.visit(node.value)
        self._write('.')
        self._write(node.attr)

    # Subscript(expr value, slice slice, expr_context ctx)
    def visit_Subscript(self, node) -> None:
        self.visit(node.value)
        self._write('[')
        if isinstance(node.slice, ast.Tuple) and node.slice.elts:
            self.visit(node.slice.elts[0])
            if len(node.slice.elts) == 1:
                self._write(', ')
            else:
                for dim in node.slice.elts[1:]:
                    self._write(', ')
                    self.visit(dim)
        elif isinstance(node.slice, ast.Slice):
            self.visit_Slice(node.slice, True)
        else:
            self.visit(node.slice)
        self._write(']')

    # Slice(expr? lower, expr? upper, expr? step)
    def visit_Slice(self, node, subscription: bool = False) -> None:
        if subscription:
            if getattr(node, 'lower', None) is not None:
                self.visit(node.lower)
            self._write(':')
            if getattr(node, 'upper', None) is not None:
                self.visit(node.upper)
            if getattr(node, 'step', None) is not None:
                self._write(':')
                self.visit(node.step)
        else:
            self._write('slice(')
            self.visit(getattr(node, "lower", None) or AST_NONE)
            self._write(', ')
            self.visit(getattr(node, "upper", None) or AST_NONE)
            self._write(', ')
            self.visit(getattr(node, "step", None) or AST_NONE)
            self._write(')')

    # Index(expr value)
    def visit_Index(self, node) -> None:
        self.visit(node.value)

    # ExtSlice(slice* dims)
    def visit_ExtSlice(self, node) -> None:
        self.visit(node.dims[0])
        if len(node.dims) == 1:
            self._write(', ')
        else:
            for dim in node.dims[1:]:
                self._write(', ')
                self.visit(dim)

    # Starred(expr value, expr_context ctx)
    def visit_Starred(self, node) -> None:
        self._write('*')
        self.visit(node.value)

    # Name(identifier id, expr_context ctx)
    def visit_Name(self, node) -> None:
        self._write(node.id)

    # List(expr* elts, expr_context ctx)
    def visit_List(self, node) -> None:
        self._write('[')
        for elt in node.elts:
            self.visit(elt)
            self._write(', ')
        self._write(']')

    # Tuple(expr *elts, expr_context ctx)
    def visit_Tuple(self, node) -> None:
        self._write('(')
        for elt in node.elts:
            self.visit(elt)
            self._write(', ')
        self._write(')')

    # NameConstant(singleton value)
    def visit_NameConstant(self, node) -> None:
        self._write(str(node.value))


class AnnotationAwareVisitor(ast.NodeVisitor):
    def visit(self, node) -> None:
        annotation = node_annotations.get(node)
        if annotation is not None:
            assert hasattr(annotation, '_fields')
            node = annotation

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
        return self.transformed

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
