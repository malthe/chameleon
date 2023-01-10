import ast
import re
import sys
from ast import Try

from .astutil import Builtin
from .astutil import ItemLookupOnAttributeErrorVisitor
from .astutil import Symbol
from .astutil import load
from .astutil import parse
from .astutil import store
from .codegen import TemplateCodeGenerator
from .codegen import reverse_builtin_map
from .codegen import template
from .compiler import Interpolator
from .exc import ExpressionError
from .parser import substitute
from .tokenize import Token
from .utils import ImportableMarker
from .utils import Markup
from .utils import lookup_attr
from .utils import resolve_dotted


DEFAULT_MARKER = ImportableMarker(__name__, "DEFAULT")

split_parts = re.compile(r'(?<!\\)\|')
match_prefix = re.compile(r'^\s*([a-z][a-z0-9\-_]*):').match
re_continuation = re.compile(r'\\\s*$', re.MULTILINE)
exc_clear = getattr(sys, "exc_clear", None)


def resolve_global(value):
    name = reverse_builtin_map.get(value)
    if name is not None:
        return Builtin(name)

    return Symbol(value)


def test(expression, engine=None, **env):
    if engine is None:
        engine = SimpleEngine()

    body = expression(store("result"), engine)
    module = ast.Module(body)
    module = ast.fix_missing_locations(module)
    env['rcontext'] = {}
    if exc_clear is not None:
        env['__exc_clear'] = exc_clear
    source = TemplateCodeGenerator(module).code
    code = compile(source, '<string>', 'exec')
    exec(code, env)
    result = env["result"]

    if isinstance(result, str):
        result = str(result)

    return result


def transform_attribute(node):
    return template(
        "lookup(object, name)",
        lookup=Symbol(lookup_attr),
        object=node.value,
        name=ast.Str(s=node.attr),
        mode="eval"
    )


class TalesExpr:
    """Base class.

    This class helps implementations for the Template Attribute
    Language Expression Syntax (TALES).

    The syntax evaluates one or more expressions, separated by '|'
    (pipe). The first expression that succeeds, is returned.

    Expression:

      expression    := (type ':')? line ('|' expression)?
      line          := .*

    Expression lines may not contain the pipe character unless
    escaped. It has a special meaning:

    If the expression to the left of the pipe fails (raises one of the
    exceptions listed in ``catch_exceptions``), evaluation proceeds to
    the expression(s) on the right.

    Subclasses must implement ``translate`` which assigns a value for
    a given expression.

    >>> class PythonPipeExpr(TalesExpr):
    ...     def translate(self, expression, target):
    ...         compiler = PythonExpr(expression)
    ...         return compiler(target, None)

    >>> test(PythonPipeExpr('foo | bar | 42'))
    42

    >>> test(PythonPipeExpr('foo|42'))
    42
    """

    exceptions = AttributeError, \
        NameError, \
        LookupError, \
        TypeError, \
        ValueError

    ignore_prefix = True

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        remaining = self.expression
        assignments = []

        while remaining:
            if self.ignore_prefix and match_prefix(remaining) is not None:
                compiler = engine.parse(remaining)
                assignment = compiler.assign_value(target)
                remaining = ""
            else:
                for m in split_parts.finditer(remaining):
                    expression = remaining[:m.start()]
                    remaining = remaining[m.end():]
                    break
                else:
                    expression = remaining
                    remaining = ""

                expression = expression.replace('\\|', '|')
                assignment = self.translate_proxy(engine, expression, target)
            assignments.append(assignment)

        if not assignments:
            if not remaining:
                raise ExpressionError("No input:", remaining)

            assignments.append(
                self.translate_proxy(engine, remaining, target)
            )

        for i, assignment in enumerate(reversed(assignments)):
            if i == 0:
                body = assignment
            else:
                body = [Try(
                    body=assignment,
                    handlers=[ast.ExceptHandler(
                        type=ast.Tuple(
                            elts=map(resolve_global, self.exceptions),
                            ctx=ast.Load()),
                        name=None,
                        body=body if exc_clear is None else body + [
                            ast.Expr(
                                ast.Call(
                                    func=load("__exc_clear"),
                                    args=[],
                                    keywords=[],
                                    starargs=None,
                                    kwargs=None,
                                )
                            )
                        ],
                    )],
                )]

        return body

    def translate_proxy(self, engine, *args):
        """Default implementation delegates to ``translate`` method."""

        return self.translate(*args)

    def translate(self, expression, target):
        """Return statements that assign a value to ``target``."""

        raise NotImplementedError(
            "Must be implemented by a subclass.")


class PathExpr(TalesExpr):
    """Path expression compiler.

    Syntax::

        PathExpr ::= Path [ '|' Path ]*
        Path ::= variable [ '/' URL_Segment ]*
        variable ::= Name

    For example::

        request/cookies/oatmeal
        nothing
        here/some-file 2001_02.html.tar.gz/foo
        root/to/branch | default

    When a path expression is evaluated, it attempts to traverse
    each path, from left to right, until it succeeds or runs out of
    paths. To traverse a path, it first fetches the object stored in
    the variable. For each path segment, it traverses from the current
    object to the subobject named by the path segment.

    Once a path has been successfully traversed, the resulting object
    is the value of the expression. If it is a callable object, such
    as a method or class, it is called.

    The semantics of traversal (and what it means to be callable) are
    implementation-dependent (see the ``translate`` method).
    """

    def translate(self, expression, target):
        raise NotImplementedError(
            "Path expressions are not yet implemented. "
            "It's unclear whether a general implementation "
            "can be devised.")


class PythonExpr(TalesExpr):
    r"""Python expression compiler.

    >>> test(PythonExpr('2 + 2'))
    4

    The Python expression is a TALES expression. That means we can use
    the pipe operator:

    >>> test(PythonExpr('foo | 2 + 2 | 5'))
    4

    To include a pipe character, use a backslash escape sequence:

    >>> test(PythonExpr(r'"\|"'))
    '|'
    """

    transform = ItemLookupOnAttributeErrorVisitor(transform_attribute)

    def parse(self, string):
        return parse(string, 'eval').body

    def translate(self, expression, target):
        # Strip spaces
        string = expression.strip()

        # Conver line continuations to newlines
        string = substitute(re_continuation, '\n', string)

        # Convert newlines to spaces
        string = string.replace('\n', ' ')

        try:
            value = self.parse(string)
        except SyntaxError as exc:
            raise ExpressionError(exc.msg, string)

        # Transform attribute lookups to allow fallback to item lookup
        self.transform.visit(value)

        return [ast.Assign(targets=[target], value=value)]


class ImportExpr:
    re_dotted = re.compile(r'^[A-Za-z.]+$')

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        string = self.expression.strip().replace('\n', ' ')
        value = template(
            "RESOLVE(NAME)",
            RESOLVE=Symbol(resolve_dotted),
            NAME=ast.Str(s=string),
            mode="eval",
        )
        return [ast.Assign(targets=[target], value=value)]


class NotExpr:
    """Negates the expression.

    >>> engine = SimpleEngine(PythonExpr)

    >>> test(NotExpr('False'), engine)
    True
    >>> test(NotExpr('True'), engine)
    False
    """

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        compiler = engine.parse(self.expression)
        body = compiler.assign_value(target)
        return body + template("target = not target", target=target)


class StructureExpr:
    """Wraps the expression result as 'structure'.

    >>> engine = SimpleEngine(PythonExpr)

    >>> test(StructureExpr('\"<tt>foo</tt>\"'), engine)
    '<tt>foo</tt>'
    """

    wrapper_class = Symbol(Markup)

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        compiler = engine.parse(self.expression)
        body = compiler.assign_value(target)
        return body + template(
            "target = wrapper(target)",
            target=target,
            wrapper=self.wrapper_class
        )


class IdentityExpr:
    """Identity expression.

    Exists to demonstrate the interface.

    >>> test(IdentityExpr('42'))
    42
    """

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        compiler = engine.parse(self.expression)
        return compiler.assign_value(target)


class StringExpr:
    """Similar to the built-in ``string.Template``, but uses an

    expression engine to support pluggable string substitution
    expressions.

    Expr string:

      string       := (text | substitution) (string)?
      substitution := ('$' variable | '${' expression '}')
      text         := .*

    In other words, an expression string can contain multiple
    substitutions. The text- and substitution parts will be
    concatenated back into a string.

    >>> test(StringExpr('Hello ${name}!'), name='world')
    'Hello world!'

    In the default configuration, braces may be omitted if the
    expression is an identifier.

    >>> test(StringExpr('Hello $name!'), name='world')
    'Hello world!'

    The ``braces_required`` flag changes this setting:

    >>> test(StringExpr('Hello $name!', True))
    'Hello $name!'

    To avoid interpolation, use two dollar symbols. Note that only a
    single symbol will appear in the output.

    >>> test(StringExpr('$${name}'))
    '${name}'

    In previous versions, it was possible to escape using a regular
    backslash coding, but this is no longer supported.

    >>> test(StringExpr(r'\\${name}'), name='Hello world!')
    '\\\\Hello world!'

    Multiple interpolations in one:

    >>> test(StringExpr("Hello ${'a'}${'b'}${'c'}!"))
    'Hello abc!'

    Here's a more involved example taken from a javascript source:

    >>> result = test(StringExpr(\"\"\"
    ... function($$, oid) {
    ...     $('#' + oid).autocomplete({source: ${'source'}});
    ... }
    ... \"\"\"))

    >>> 'source: source' in result
    True

    As noted previously, the double-dollar escape also affects
    non-interpolation expressions.

    >>> 'function($, oid)' in result
    True

    >>> test(StringExpr('test ${1}${2}'))
    'test 12'

    >>> test(StringExpr('test $${1}${2}'))
    'test ${1}2'

    >>> test(StringExpr('test $$'))
    'test $'

    >>> test(StringExpr('$$.ajax(...)'))
    '$.ajax(...)'

    >>> test(StringExpr('test $$ ${1}'))
    'test $ 1'

    In the above examples, the expression is evaluated using the
    dummy engine which just returns the input as a string.

    As an example, we'll implement an expression engine which
    instead counts the number of characters in the expresion and
    returns an integer result.

    >>> class engine:
    ...     @staticmethod
    ...     def parse(expression, char_escape=None):
    ...         class compiler:
    ...             @staticmethod
    ...             def assign_text(target):
    ...                 return [
    ...                     ast.Assign(
    ...                         targets=[target],
    ...                         value=ast.Num(n=len(expression))
    ...                     )]
    ...
    ...         return compiler

    This will demonstrate how the string expression coerces the
    input to a string.

    >>> expr = StringExpr(
    ...    'There are ${hello world} characters in \"hello world\"')

    We evaluate the expression using the new engine:

    >>> test(expr, engine)
    'There are 11 characters in \"hello world\"'
    """

    def __init__(self, expression, braces_required=False):
        # The code relies on the expression being a token string
        if not isinstance(expression, Token):
            expression = Token(expression, 0)

        self.translator = Interpolator(expression, braces_required)

    def __call__(self, name, engine):
        return self.translator(name, engine)


class ProxyExpr(TalesExpr):
    braces_required = False

    def __init__(self, name, expression, ignore_prefix=True):
        super().__init__(expression)
        self.ignore_prefix = ignore_prefix
        self.name = name

    def translate_proxy(self, engine, expression, target):
        translator = Interpolator(expression, self.braces_required)
        assignment = translator(target, engine)

        return assignment + [
            ast.Assign(targets=[target], value=ast.Call(
                func=load(self.name),
                args=[target],
                keywords=[],
                starargs=None,
                kwargs=None
            ))
        ]


class ExistsExpr:
    """Boolean wrapper.

    Return 0 if the expression results in an exception, otherwise 1.

    As a means to generate exceptions, we set up an expression engine
    which evaluates the provided expression using Python:

    >>> engine = SimpleEngine(PythonExpr)

    >>> test(ExistsExpr('int(0)'), engine)
    1
    >>> test(ExistsExpr('int(None)'), engine)
    0

    """

    exceptions = AttributeError, LookupError, TypeError, NameError

    def __init__(self, expression):
        self.expression = expression

    def __call__(self, target, engine):
        ignore = store("_ignore")
        compiler = engine.parse(self.expression, False)
        body = compiler.assign_value(ignore)

        classes = map(resolve_global, self.exceptions)

        return [
            Try(
                body=body,
                handlers=[ast.ExceptHandler(
                    type=ast.Tuple(elts=classes, ctx=ast.Load()),
                    name=None,
                    body=template("target = 0", target=target),
                )],
                orelse=template("target = 1", target=target)
            )
        ]


class ExpressionParser:
    def __init__(self, factories, default):
        self.factories = factories
        self.default = default

    def __call__(self, expression):
        m = match_prefix(expression)
        if m is not None:
            prefix = m.group(1)
            expression = expression[m.end():]
        else:
            prefix = self.default

        try:
            factory = self.factories[prefix]
        except KeyError as exc:
            raise LookupError(
                "Unknown expression type: %s." % str(exc)
            )

        return factory(expression)


class SimpleEngine:
    expression = PythonExpr

    def __init__(self, expression=None):
        if expression is not None:
            self.expression = expression

    def parse(self, string, handle_errors=False, char_escape=None):
        compiler = self.expression(string)
        return SimpleCompiler(compiler, self)


class SimpleCompiler:
    def __init__(self, compiler, engine):
        self.compiler = compiler
        self.engine = engine

    def assign_text(self, target):
        """Assign expression string as a text value."""

        return self._assign_value_and_coerce(target, "str")

    def assign_value(self, target):
        """Assign expression string as object value."""

        return self.compiler(target, self.engine)

    def _assign_value_and_coerce(self, target, builtin):
        return self.assign_value(target) + template(
            "target = builtin(target)",
            target=target,
            builtin=builtin
        )
