from __future__ import annotations

import ast
import builtins
import collections
import functools
import itertools
import logging
import pickle
import re
import sys
import textwrap
import threading

from chameleon.astutil import Builtin
from chameleon.astutil import Comment
from chameleon.astutil import NameLookupRewriteVisitor
from chameleon.astutil import Node
from chameleon.astutil import Static
from chameleon.astutil import Symbol
from chameleon.astutil import TokenRef
from chameleon.astutil import load
from chameleon.astutil import param
from chameleon.astutil import store
from chameleon.astutil import subscript
from chameleon.codegen import TemplateCodeGenerator
from chameleon.codegen import template
from chameleon.exc import ExpressionError
from chameleon.exc import TranslationError
from chameleon.i18n import simple_translate
from chameleon.nodes import And
from chameleon.nodes import Assignment
from chameleon.nodes import Context
from chameleon.nodes import Equals
from chameleon.nodes import Is
from chameleon.nodes import IsNot
from chameleon.nodes import Logical
from chameleon.nodes import Module
from chameleon.nodes import Substitution
from chameleon.nodes import Text
from chameleon.nodes import Value
from chameleon.parser import groupdict
from chameleon.tal import NAME
from chameleon.tal import ErrorInfo
from chameleon.tokenize import Token
from chameleon.utils import ListDictProxy
from chameleon.utils import char2entity
from chameleon.utils import decode_htmlentities
from chameleon.utils import join
from chameleon.utils import safe_native


log = logging.getLogger('chameleon.compiler')

# Disallowing the use of the following symbols to avoid misunderstandings.
COMPILER_INTERNALS_OR_DISALLOWED = {
    "econtext",
    "rcontext",
}

RE_MANGLE = re.compile(r'[^\w_]')
RE_NAME = re.compile('^%s$' % NAME)


def identifier(prefix: str, suffix: str | None = None) -> str:
    return "__{}_{}".format(prefix, mangle(suffix or id(prefix)))


def mangle(string: int | str) -> str:
    return RE_MANGLE.sub('_', str(string)).replace('\n', '').replace('-', '_')


def load_econtext(name):
    return template("getname(KEY)", KEY=ast.Constant(name), mode="eval")


def store_econtext(name: object) -> ast.Subscript:
    name = str(name)
    return subscript(name, load("econtext"), ast.Store())


def store_rcontext(name: object) -> ast.Subscript:
    name = str(name)
    return subscript(name, load("rcontext"), ast.Store())


def eval_token(token):
    try:
        line, column = token.location
    except AttributeError:
        line, column = 0, 0

    string = safe_native(token)

    return template(
        "(string, line, col)",
        string=ast.Constant(string),
        line=ast.Constant(line),
        col=ast.Constant(column),
        mode="eval"
    )


def indent(s: str | None) -> str:
    return textwrap.indent(s, "    ") if s else ""


emit_node_if_non_trivial = template(is_func=True, func_args=('node',),
                                    source=r"""
    if node is not None:
        __append(node)
""")


emit_bool = template(is_func=True,
                     func_args=('target', 's', 'default_marker', 'default'),
                     func_defaults=(None, None), source=r"""
    if target is default_marker:
        target = default
    elif target:
        target = s
    else:
        target = None""")


emit_convert = template(is_func=True,
                        func_args=('target', 'encoded', 'str', 'type',
                                   'default_marker', 'default'),
                        func_defaults=(bytes, str, type, None),
                        source=r"""
    if target is None:
        pass
    elif target is default_marker:
        target = default
    else:
        __tt = type(target)

        if __tt is encoded:
            target = decode(target)
        elif __tt is not str:
            if __tt is int or __tt is float:
                target = str(target)
            else:
                __markup = getattr(target, "__html__", None)
                if __markup is None:
                    __converted = translate(
                        target,
                        domain=__i18n_domain,
                        context=__i18n_context,
                        target_language=target_language
                    )
                    target = str(target) \
                        if target is __converted \
                        else __converted
                else:
                    target = __markup()""")


emit_func_convert = template(
    is_func=True, func_args=(
        'func', 'encoded', 'str', 'type'), func_defaults=(
            bytes, str, type), source=r"""
    def func(target):
        if target is None:
            return

        __tt = type(target)

        if __tt is encoded:
            target = decode(target)
        elif __tt is not str:
            if __tt is int or __tt is float:
                target = str(target)
            else:
                __markup = getattr(target, "__html__", None)
                if __markup is None:
                    __converted = translate(
                        target,
                        domain=__i18n_domain,
                        context=__i18n_context,
                        target_language=target_language
                    )
                    target = str(target) \
                        if target is __converted \
                        else __converted
                else:
                    target = __markup()

        return target"""
)


emit_translate = template(is_func=True,
                          func_args=('target', 'msgid',
                                     'default'),
                          func_defaults=(None,),
                          source=r"""
    target = translate(
        msgid,
        default=default,
        domain=__i18n_domain,
        context=__i18n_context,
        target_language=target_language
    )""")


emit_func_convert_and_escape = template(
    is_func=True,
    func_args=('func', 'str', 'type', 'encoded'),
    func_defaults=(str, type, bytes,),
    source=r"""
    def func(target, quote, quote_entity, default, default_marker):
        if target is None:
            return

        if target is default_marker:
            return default

        __tt = type(target)

        if __tt is encoded:
            target = decode(target)
        elif __tt is not str:
            if __tt is int or __tt is float:
                return str(target)
            __markup = getattr(target, "__html__", None)
            if __markup is None:
                __converted = translate(
                    target,
                    domain=__i18n_domain,
                    context=__i18n_context,
                    target_language=target_language
                )
                target = str(target) if target is __converted \
                         else __converted
            else:
                return __markup()

        if target is not None:
            try:
                escape = __re_needs_escape(target) is not None
            except TypeError:
                pass
            else:
                if escape:
                    # Character escape
                    if '&' in target:
                        target = target.replace('&', '&amp;')
                    if '<' in target:
                        target = target.replace('<', '&lt;')
                    if '>' in target:
                        target = target.replace('>', '&gt;')
                    if quote is not None and quote in target:
                        target = target.replace(quote, quote_entity)

        return target""")


class EmitText(Node):
    """Append text to output."""

    _fields = "s",


class TranslationContext(Node):
    """Set a local output context.

    This is used for the translation machinery.
    """

    _fields = "body", "append", "stream"

    body = None
    append = None
    stream = None


class Interpolator:
    braces_required_regex = re.compile(
        r'\$({(?P<expression>.*)})', re.DOTALL
    )

    braces_optional_regex = re.compile(
        r'\$({(?P<expression>.*)}|(?P<variable>[A-Za-z][A-Za-z0-9_]*))',
        re.DOTALL,
    )

    def __init__(
        self,
        expression,
        braces_required,
        translate: bool = False,
        decode_htmlentities: bool = False,
    ) -> None:
        self.expression = expression
        self.regex = (
            self.braces_required_regex
            if braces_required
            else self.braces_optional_regex
        )
        self.translate = translate
        self.decode_htmlentities = decode_htmlentities

    def __call__(self, name, engine):
        """The strategy is to find possible expression strings and
        call the ``validate`` function of the parser to validate.

        For every possible starting point, the longest possible
        expression is tried first, then the second longest and so
        forth.

        Example 1:

          ${'expressions use the ${<expression>} format'}

        The entire expression is attempted first and it is also the
        only one that validates.

        Example 2:

          ${'Hello'} ${'world!'}

        Validation of the longest possible expression (the entire
        string) will fail, while the second round of attempts,
        ``${'Hello'}`` and ``${'world!'}`` respectively, validate.

        """

        body = []
        nodes = []
        text = self.expression

        expr_map = {}
        translate = self.translate

        while text:
            matched = text

            m = self.regex.search(matched)
            if m is None:
                text = text.replace('$$', '$')
                nodes.append(ast.Constant(text))
                break

            part = text[:m.start()]
            text = text[m.start():]

            if part:
                i = 0
                length = len(part)
                while i < length and part[-i - 1] == '$':
                    i += 1
                skip = i & 1
                part = part.replace('$$', '$')
                node = ast.Constant(part)
                nodes.append(node)
                if skip:
                    text = text[1:]
                    continue

            if not body:
                target = name
            else:
                target = store("%s_%d" % (name.id, text.pos))

            while True:
                d = groupdict(m, matched)
                string = d["expression"] or d.get("variable") or ""

                if self.decode_htmlentities:
                    string = decode_htmlentities(string)

                if string:
                    try:
                        compiler = engine.parse(string)
                        body += compiler.assign_text(target)
                    except ExpressionError:
                        matched = matched[m.start():m.end() - 1]
                        m = self.regex.search(matched)
                        if m is None:
                            raise

                        continue
                else:
                    s = m.group()
                    assign = ast.Assign(
                        targets=[target], value=ast.Constant(s))
                    body += [assign]

                break

            # If one or more expressions are not simple names, we
            # disable translation.
            if RE_NAME.match(string) is None:
                translate = False

            # if this is the first expression, use the provided
            # assignment name; otherwise, generate one (here based
            # on the string position)
            node = load(target.id)
            nodes.append(node)

            expr_map[node] = safe_native(string)

            text = text[len(m.group()):]

        if len(nodes) == 1:
            target = nodes[0]

            if (
                translate
                and isinstance(target, ast.Constant)
                and isinstance(target.value, str)
            ):
                target = template(
                    "translate(msgid, domain=__i18n_domain, context=__i18n_context, target_language=target_language)",  # noqa:  E501 line too long
                    msgid=target,
                    mode="eval",
                )
        else:
            if translate:
                formatting_string = ""
                keys = []
                values = []

                for node in nodes:
                    if (
                        isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                    ):
                        formatting_string += node.value
                    else:
                        string = expr_map[node]
                        formatting_string += "${%s}" % string
                        keys.append(ast.Constant(string))
                        values.append(node)

                target = template(
                    "translate(msgid, mapping=mapping, domain=__i18n_domain, context=__i18n_context, target_language=target_language)",   # noqa:  E501 line too long
                    msgid=ast.Constant(
                        formatting_string),
                    mapping=ast.Dict(
                        keys=keys,
                        values=values),
                    mode="eval")
            else:
                nodes = [
                    node
                    if (
                        isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                    ) else
                    template(
                        "NODE if NODE is not None else ''",
                        NODE=node, mode="eval"
                    )
                    for node in nodes
                ]

                target = ast.BinOp(
                    left=ast.Constant("%s" * len(nodes)),
                    op=ast.Mod(),
                    right=ast.Tuple(elts=nodes, ctx=ast.Load()))

        body += [ast.Assign(targets=[name], value=target)]
        return body


class ExpressionEngine:
    """Expression engine.

    This test demonstrates how to configure and invoke the engine.

    >>> from chameleon import tales
    >>> parser = tales.ExpressionParser({
    ...     'python': tales.PythonExpr,
    ...     'not': tales.NotExpr,
    ...     'exists': tales.ExistsExpr,
    ...     'string': tales.StringExpr,
    ...     }, 'python')

    >>> engine = ExpressionEngine(parser)

    An expression evaluation function:

    >>> eval = lambda expression: tales.test(
    ...     tales.IdentityExpr(expression), engine)

    We have provided 'python' as the default expression type. This
    means that when no prefix is given, the expression is evaluated as
    a Python expression:

    >>> eval('not False')
    True

    Note that the ``type`` prefixes bind left. If ``not`` and
    ``exits`` are two expression type prefixes, consider the
    following::

    >>> eval('not: exists: int(None)')
    True

    The pipe operator binds right. In the following example, but
    arguments are evaluated against ``not: exists: ``.

    >>> eval('not: exists: help')
    False
    """

    supported_char_escape_set = {'&', '<', '>'}

    def __init__(
        self,
        parser,
        char_escape=(),
        default=None,
        default_marker=None,
        literal_false: bool = True,
    ) -> None:
        self._parser = parser
        self._char_escape = char_escape
        self._default = default
        self._default_marker = default_marker
        self._literal_false = literal_false

    def __call__(self, string, target):
        # BBB: This method is deprecated. Instead, a call should first
        # be made to ``parse`` and then one of the assignment methods
        # ("value" or "text").

        compiler = self.parse(string)
        return compiler(string, target)

    def parse(self, string, handle_errors: bool = True, char_escape=None):
        expression = self._parser(string)
        compiler = self.get_compiler(
            expression, string, handle_errors, char_escape
        )
        return ExpressionCompiler(compiler, self)

    def get_compiler(self, expression, string, handle_errors, char_escape):
        if char_escape is None:
            char_escape = self._char_escape

        def compiler(target, engine, result_type=None, *args):
            stmts = expression(target, engine)

            if result_type is not None:
                method = getattr(self, '_convert_%s' % result_type)
                steps = method(target, char_escape, *args)

                if not self._literal_false:
                    steps = [
                        ast.If(
                            ast.UnaryOp(
                                op=ast.Not(),
                                operand=target
                            ),
                            [ast.Assign(
                                targets=[store(target.id)],
                                value=load('None')
                            )],
                            steps
                        )
                    ]

                stmts.extend(steps)

            if handle_errors and isinstance(string, Token):
                stmts.insert(0, TokenRef(string.strip()))

            return stmts

        return compiler

    def _convert_bool(self, target, char_escape, s):
        """Converts value given by ``target`` to a string ``s`` if the
        target is a true value, otherwise ``None``.
        """

        return emit_bool(
            target, ast.Constant(s),
            default=self._default,
            default_marker=self._default_marker
        )

    def _convert_structure(self, target, char_escape):
        """Converts value given by ``target`` to structure output."""

        return emit_convert(
            target,
            default=self._default,
            default_marker=self._default_marker,
        )

    def _convert_text(self, target, char_escape):
        """Converts value given by ``target`` to text."""

        if not char_escape:
            return self._convert_structure(target, char_escape)

        # This is a cop-out - we really only support a very select
        # set of escape characters
        other = set(char_escape) - self.supported_char_escape_set

        if other:
            for supported in '"', '\'', '':
                if supported in char_escape:
                    quote = supported
                    break
            else:
                raise RuntimeError(
                    "Unsupported escape set: %s." % repr(char_escape)
                )
        else:
            quote = '\0'

        entity = char2entity(quote or '\0')

        return template(
            "TARGET = __quote(TARGET, QUOTE, Q_ENTITY, DEFAULT, MARKER)",
            TARGET=target,
            QUOTE=ast.Constant(quote),
            Q_ENTITY=ast.Constant(entity),
            DEFAULT=self._default,
            MARKER=self._default_marker,
        )


class ExpressionCompiler:
    def __init__(self, compiler, engine) -> None:
        self.compiler = compiler
        self.engine = engine

    def assign_bool(self, target, s):
        return self.compiler(target, self.engine, "bool", s)

    def assign_text(self, target):
        return self.compiler(target, self.engine, "text")

    def assign_value(self, target):
        return self.compiler(target, self.engine)


class ExpressionEvaluator:
    """Evaluates dynamic expression.

    This is not particularly efficient, but supported for legacy
    applications.

    >>> from chameleon import tales
    >>> parser = tales.ExpressionParser({'python': tales.PythonExpr}, 'python')
    >>> engine = functools.partial(ExpressionEngine, parser)

    >>> evaluator = ExpressionEvaluator(engine, {
    ...     'foo': 'bar',
    ... })

    We'll use the following convenience function to test the expression
    evaluator.
    >>> from chameleon.utils import Scope
    >>> def evaluate(d, *args):
    ...     return evaluator(Scope(d), *args)

    The evaluation function is passed the local and remote context,
    the expression type and finally the expression.

    >>> evaluate({'boo': 'baz'}, {}, 'python', 'foo + boo')
    'barbaz'

    The cache is now primed:

    >>> evaluate({'boo': 'baz'}, {}, 'python', 'foo + boo')
    'barbaz'

    Note that the call method supports currying of the expression
    argument:

    >>> python = evaluate({'boo': 'baz'}, {}, 'python')
    >>> python('foo + boo')
    'barbaz'

    """

    __slots__ = "_engine", "_cache", "_names", "_builtins"

    def __init__(self, engine, builtins):
        self._engine = engine
        self._names, self._builtins = zip(*builtins.items())
        self._cache = {}

    def __call__(self, econtext, rcontext, expression_type, string=None):
        if string is None:
            return functools.partial(
                self.__call__, econtext, rcontext, expression_type
            )

        expression = "{}:{}".format(expression_type, string)

        try:
            evaluate = self._cache[expression]
        except KeyError:
            assignment = Assignment(["_result"], expression, True)
            module = Module("evaluate", Context(assignment))

            compiler = Compiler(
                self._engine, module, "<string>", string,
                ('econtext', 'rcontext') + self._names
            )

            env = {}
            exec(compiler.code, env)
            evaluate = self._cache[expression] = env["evaluate"]

        evaluate(econtext, rcontext, *self._builtins)
        return econtext['_result']


class NameTransform:
    """
    >>> nt = NameTransform(
    ...     set(('foo', 'bar', )), {'boo': 'boz'},
    ...     ('econtext', ),
    ... )

    >>> def test(name):
    ...     rewritten = nt(load(name))
    ...     module = ast.Module([ast.fix_missing_locations(rewritten)], [])
    ...     codegen = TemplateCodeGenerator(module)
    ...     return codegen.code

    Any odd name:

    >>> test('frobnitz')
    "getname('frobnitz')"

    A 'builtin' name will first be looked up via ``get`` allowing fall
    back to the global builtin value:

    >>> test('foo')
    "get('foo', foo)"

    Internal names (with two leading underscores) are left alone:

    >>> test('__internal')
    '__internal'

    Compiler internals or disallowed names:

    >>> test('econtext')
    'econtext'

    Aliased names:

    >>> test('boo')
    'boz'

    """

    def __init__(self, builtins, aliases, internals) -> None:
        self.builtins = builtins
        self.aliases = aliases
        self.internals = internals

    def __call__(self, node):
        name = node.id

        # Don't rewrite names that begin with an underscore; they are
        # internal and can be assumed to be locally defined. This
        # policy really should be part of the template program, not
        # defined here in the compiler.
        if name.startswith('__') or name in self.internals:
            return node

        # Some expressions allow setting variables which we transform to
        # storing them as template context.
        if isinstance(node.ctx, ast.Store):
            return store_econtext(name)

        aliased = self.aliases.get(name)
        if aliased is not None:
            return load(aliased)

        # If the name is a Python global, first try acquiring it from
        # the dynamic context, then fall back to the global.
        if name in self.builtins:
            return template(
                "get(key, name)",
                mode="eval",
                key=ast.Constant(name),
                name=Builtin(name),
            )

        # Otherwise, simply acquire it from the dynamic context.
        return load_econtext(name)


class ExpressionTransform:
    """Internal wrapper to transform expression nodes into assignment
    statements.

    The node input may use the provided expression engine, but other
    expression node types are supported such as ``Builtin`` which
    simply resolves a built-in name.

    Used internally be the compiler.
    """

    loads_symbol = Symbol(pickle.loads)

    def __init__(
        self, engine_factory, cache, visitor, strict: bool = True
    ) -> None:
        self.engine_factory = engine_factory
        self.cache = cache
        self.strict = strict
        self.visitor = visitor

    def __call__(self, expression, target):
        if isinstance(target, str):
            target = store(target)

        try:
            stmts = self._translate(expression, target)
        except ExpressionError as exc:
            if self.strict:
                raise

            p = pickle.dumps(exc, -1)

            stmts = template(
                "__exc = loads(p)", loads=self.loads_symbol, p=ast.Constant(p)
            )

            stmts += [
                TokenRef(exc.token),
                ast.Raise(exc=load("__exc"))
            ]

        # Apply visitor to each statement
        stmts = [self.visitor(stmt) for stmt in stmts]

        return stmts

    def _translate(self, expression, target):
        if isinstance(target, str):
            target = store(target)

        cached = self.cache.get(expression)

        if cached is not None:
            stmts = [ast.Assign(targets=[target], value=cached)]
        elif isinstance(expression, ast.expr):
            stmts = [ast.Assign(targets=[target], value=expression)]
        else:
            # The engine interface supports simple strings, which
            # default to expression nodes
            if isinstance(expression, str):
                expression = Value(expression, True)

            kind = type(expression).__name__
            visitor = getattr(self, "visit_%s" % kind)
            stmts = visitor(expression, target)

            # Add comment
            target_id = getattr(target, "id", target)
            comment = Comment(" {!r} -> {}".format(expression, target_id))
            stmts.insert(0, comment)

        return stmts

    def visit_Value(self, node, target):
        engine = self.engine_factory(
            default=node.default,
            default_marker=node.default_marker
        )
        compiler = engine.parse(node.value)
        return compiler.assign_value(target)

    def visit_Copy(self, node, target):
        return self._translate(node.expression, target)

    def visit_Substitution(self, node, target):
        engine = self.engine_factory(
            default=node.default,
            default_marker=node.default_marker,
            literal_false=node.literal_false,
        )
        compiler = engine.parse(node.value, char_escape=node.char_escape)
        return compiler.assign_text(target)

    def visit_Negate(self, node, target):
        return self._translate(node.value, target) + \
            template("TARGET = not TARGET", TARGET=target)

    def visit_BinOp(self, node, target):
        expression = self._translate(node.left, "__expression")
        value = self._translate(node.right, "__value")

        op = {
            Is: "is",
            IsNot: "is not",
            Equals: "==",
        }[node.op]
        return expression + value + \
            template("TARGET = __expression %s __value" % op, TARGET=target)

    def visit_Boolean(self, node, target):
        engine = self.engine_factory(
            default=node.default,
            default_marker=node.default_marker,
        )
        compiler = engine.parse(node.value)
        return compiler.assign_bool(target, node.s)

    def visit_Interpolation(self, node, target):
        expr = node.value
        if isinstance(expr, Substitution):
            engine = self.engine_factory(
                char_escape=expr.char_escape,
                default=expr.default,
                default_marker=expr.default_marker,
                literal_false=expr.literal_false,
            )
        elif isinstance(expr, Value):
            engine = self.engine_factory(
                default=expr.default,
                default_marker=expr.default_marker
            )
        else:
            raise RuntimeError("Bad value: %r." % node.value)

        interpolator = Interpolator(
            expr.value, node.braces_required,
            translate=node.translation,
            decode_htmlentities=True
        )
        compiler = engine.get_compiler(interpolator, expr.value, True, ())
        return compiler(target, engine, "text")

    def visit_Replace(self, node, target):
        stmts = self._translate(node.value, target)
        return stmts + template(
            "if TARGET: TARGET = S",
            TARGET=target,
            S=ast.Constant(node.s)
        )

    def visit_Translate(self, node, target):
        if node.msgid is not None:
            msgid = ast.Constant(node.msgid)
        else:
            msgid = target
        return self._translate(node.node, target) + \
            emit_translate(target, msgid, default=target)

    def visit_Static(self, node, target):
        return [ast.Assign(targets=[target], value=node)]

    def visit_Builtin(self, node, target):
        return [ast.Assign(targets=[target], value=node)]

    def visit_Symbol(self, node, target):
        return template("TARGET = SYMBOL", TARGET=target, SYMBOL=node)


class Compiler:
    """Generic compiler class.

    Iterates through nodes and yields Python statements which form a
    template program.
    """

    defaults = {
        'translate': Symbol(simple_translate),
        'decode': Builtin("str"),
        'on_error_handler': Builtin("str"),
    }

    lock = threading.Lock()

    global_builtins = set(builtins.__dict__)

    def __init__(
        self,
        engine_factory,
        node,
        filename,
        source,
        builtins={},
        strict=True,
        stream_factory=list,
    ):
        self._scopes = [set()]
        self._expression_cache = {}
        self._translations = []
        self._builtins = builtins
        self._aliases = [{}]
        self._macros = []
        self._current_slot = []

        # Prepare stream factory (callable)
        self._new_list = (
            ast.List([], ast.Load()) if stream_factory is list else
            ast.Call(
                ast.Symbol(stream_factory),
                args=[],
                kwargs=[],
                lineno=None,
            )
        )

        internals = COMPILER_INTERNALS_OR_DISALLOWED | set(self.defaults)

        transform = NameTransform(
            self.global_builtins | set(builtins),
            ListDictProxy(self._aliases),
            internals,
        )

        self._visitor = visitor = NameLookupRewriteVisitor(transform)

        self._engine = ExpressionTransform(
            engine_factory,
            self._expression_cache,
            visitor,
            strict=strict,
        )

        module = ast.Module([], [])
        module.body += self.visit(node)
        ast.fix_missing_locations(module)

        class Generator(TemplateCodeGenerator):
            scopes = [TranslationContext()]
            tokens = []

            def visit_EmitText(self, node) -> ast.AST:
                append = load(self.scopes[-1].append or "__append")
                expr = ast.Expr(ast.Call(
                    func=append,
                    args=[ast.Constant(node.s)],
                    keywords=[],
                ))
                return self.visit(expr)  # type: ignore[no-any-return]

            def visit_Name(self, node: ast.Name) -> ast.AST:
                if isinstance(node.ctx, ast.Load):
                    scope = self.scopes[-1]
                    for name in ("append", "stream"):
                        if node.id == f"__{name}":
                            identifier = getattr(scope, name, None)
                            if identifier:
                                return load(identifier)
                return node

            def visit_TranslationContext(self, node) -> list[ast.AST]:
                self.scopes.append(node)
                stmts = list(map(self.visit, node.body))
                self.scopes.pop()
                return stmts

            def visit_TokenRef(self, node: TokenRef) -> ast.AST:
                self.tokens.append((node.token.pos, len(node.token)))
                assignment = ast.Assign(
                    [store("__token")],
                    ast.Constant(node.token.pos),
                )
                ast.copy_location(assignment, node)
                ast.fix_missing_locations(assignment)
                return assignment

        generator = Generator(module)
        tokens = [
            Token(source[pos:pos + length], pos, source)
            for pos, length in generator.tokens
        ]
        token_map_def = "__tokens = {" + ", ".join("%d: %r" % (
            token.pos,
            (token, ) + token.location
        ) for token in tokens) + "}"

        self.code = "\n".join((
            "__filename = %r\n" % filename,
            token_map_def,
            generator.code
        ))

    def visit(self, node):
        if node is None:
            return ()
        kind = type(node).__name__
        visitor = getattr(self, "visit_%s" % kind)
        iterator = visitor(node)
        result = []
        for key, group in itertools.groupby(
                iterator, lambda node: node.__class__):
            nodes = list(group)
            if key is EmitText:
                text = join(node.s for node in nodes)
                nodes = [EmitText(text)]
            if key is TokenRef:
                nodes = [nodes[-1]]
            result.extend(nodes)
        return result

    def visit_Sequence(self, node):
        for item in node.items:
            yield from self.visit(item)

    def visit_Element(self, node):
        yield from self.visit(node.start)

        yield from self.visit(node.content)

        if node.end is not None:
            yield from self.visit(node.end)

    def visit_Module(self, node):
        body = []
        body += template("import re")
        body += template("import functools")
        body += template("from itertools import chain as __chain")
        body += template("from sys import intern")
        body += template("__default = intern('__default__')")
        body += template("__marker = object()")
        body += template(
            "g_re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)')"
        )
        body += template(
            r"g_re_needs_escape = re.compile(r'[&<>\"\']').search")

        body += template(
            r"__re_whitespace = "
            r"functools.partial(re.compile('\\s+').sub, ' ')",
        )

        # Visit module content
        program = self.visit(node.program)

        body += [ast.FunctionDef(
            name=node.name,
            args=ast.arguments(
                args=[param(b) for b in self._builtins],
                defaults=[],
                kwonlyargs=[],
                posonlyargs=[],
            ),
            body=program,
            decorator_list=[],
            lineno=None,
        )]

        return body

    def visit_MacroProgram(self, node):
        functions = []

        # Visit defined macros
        macros = getattr(node, "macros", ())
        names = []
        for macro in macros:
            stmts = self.visit(macro)
            function = stmts[-1]
            names.append(function.name)
            functions += stmts

        # Return function dictionary
        functions += [ast.Return(value=ast.Dict(
            keys=[ast.Constant(name) for name in names],
            values=[load(name) for name in names],
        ))]

        return functions

    def visit_Context(self, node):
        return template("getname = econtext.get_name") + \
            template("get = econtext.get") + \
            self.visit(node.node)

    def visit_Macro(self, node):
        body = []

        # Initialization
        body += template("__append = __stream.append")
        body += template("__re_amp = g_re_amp")
        body += template("__token = None")
        body += template("__re_needs_escape = g_re_needs_escape")

        body += emit_func_convert("__convert")
        body += emit_func_convert_and_escape("__quote")

        # Resolve defaults
        for name in self.defaults:
            body += template(
                "NAME = econtext[KEY]",
                NAME=name, KEY=ast.Constant("__" + name)
            )

        # Internal set of defined slots
        self._slots = set()

        # Visit macro body
        nodes = list(itertools.chain(*tuple(map(self.visit, node.body))))

        # Slot resolution
        for name in self._slots:
            body += template(
                "try: NAME = econtext[KEY].pop()\n"
                "except: NAME = None",
                KEY=ast.Constant(name), NAME=store(name))

        exc = template(
            "exc_info()[1]", exc_info=Symbol(sys.exc_info), mode="eval"
        )

        exc_handler = template(
            "if pos is not None: rcontext.setdefault('__error__', [])."
            "append(token + (__filename, exc, ))",
            exc=exc,
            token=template("__tokens[pos]", pos="__token", mode="eval"),
            pos="__token"
        ) + template("raise")

        # Wrap visited nodes in try-except error handler.
        body += [
            ast.Try(
                body=nodes,
                handlers=[ast.ExceptHandler(body=exc_handler)],
                finalbody=[],
                orelse=[],
            )
        ]

        function_name = "render" if node.name is None else \
                        "render_%s" % mangle(node.name)

        function = ast.FunctionDef(
            name=function_name, args=ast.arguments(
                args=[
                    param("__stream"),
                    param("econtext"),
                    param("rcontext"),
                    param("__i18n_domain"),
                    param("__i18n_context"),
                    param("target_language"),
                ],
                defaults=[load("None"), load("None"), load("None")],
                kwonlyargs=[],
                posonlyargs=[],
            ),
            body=body,
            decorator_list=[],
            lineno=None,
        )

        yield function

    def visit_Text(self, node):
        yield EmitText(node.value)

    # TODO Refactor!

    def visit_Domain(self, node):
        backup = "__previous_i18n_domain_%s" % mangle(id(node))
        return template("BACKUP = __i18n_domain", BACKUP=backup) + \
            template("__i18n_domain = NAME", NAME=ast.Constant(node.name)) + \
            self.visit(node.node) + \
            template("__i18n_domain = BACKUP", BACKUP=backup)

    def visit_Target(self, node):
        backup = "__previous_i18n_target_%s" % mangle(id(node))
        tmp = "__tmp_%s" % mangle(id(node))
        return template("BACKUP = target_language", BACKUP=backup) + \
            self._engine(node.expression, store(tmp)) + \
            [ast.Assign([store("target_language")], load(tmp))] + \
            self.visit(node.node) + \
            template("target_language = BACKUP", BACKUP=backup)

    def visit_TxContext(self, node):
        backup = "__previous_i18n_context_%s" % mangle(id(node))
        return template("BACKUP = __i18n_context", BACKUP=backup) + \
            template("__i18n_context = NAME", NAME=ast.Constant(node.name)) + \
            self.visit(node.node) + \
            template("__i18n_context = BACKUP", BACKUP=backup)

    def visit_OnError(self, node):
        body = []

        fallback = identifier("__fallback")
        body += template("fallback = len(__stream)", fallback=fallback)

        self._enter_assignment((node.name, ))
        fallback_body = self.visit(node.fallback)
        self._leave_assignment((node.name, ))

        error_assignment = template(
            "econtext[key] = cls(__exc, __tokens[__token][1:3])\n"
            "if handler is not None: handler(__exc)",
            cls=ErrorInfo,
            handler=load("on_error_handler"),
            key=ast.Constant(node.name),
        )

        body += [ast.Try(
            body=self.visit(node.node),
            handlers=[ast.ExceptHandler(
                type=ast.Tuple(elts=[Builtin("Exception")], ctx=ast.Load()),
                name="__exc",
                body=(error_assignment +
                      template("del __stream[fallback:]", fallback=fallback) +
                      fallback_body
                      ),
            )],
            finalbody=[],
            orelse=[],
        )]

        return body

    def visit_Content(self, node):
        name = "__content"
        body = self._engine(node.expression, store(name))

        if node.translate:
            body += emit_translate(name, name)

        if node.char_escape:
            body += template(
                "NAME=__quote(NAME, None, '\255', None, None)",
                NAME=name,
            )
        else:
            body += template("NAME = __convert(NAME)", NAME=name)

        body += template("if NAME is not None: __append(NAME)", NAME=name)

        return body

    def visit_Interpolation(self, node):
        name = identifier("content")
        return self._engine(node, name) + \
            emit_node_if_non_trivial(name)

    def visit_Alias(self, node):
        assert len(node.names) == 1
        name = node.names[0]
        target = self._aliases[-1][name] = identifier(name, id(node))
        return self._engine(node.expression, target)

    def visit_Assignment(self, node):
        for name in node.names:
            if name in COMPILER_INTERNALS_OR_DISALLOWED:
                raise TranslationError(
                    "Name disallowed by compiler.", name
                )

            if name.startswith('__'):
                raise TranslationError(
                    "Name disallowed by compiler (double underscore).",
                    name
                )

        assignment = self._engine(node.expression, store("__value"))

        if len(node.names) != 1:
            target = ast.Tuple(
                elts=[store_econtext(name) for name in node.names],
                ctx=ast.Store(),
            )
        else:
            target = store_econtext(node.names[0])

        assignment.append(ast.Assign(targets=[target], value=load("__value")))

        for name in node.names:
            if not node.local:
                assignment += template(
                    "rcontext[KEY] = __value", KEY=ast.Constant(
                        str(name)))

        return assignment

    def visit_Define(self, node):
        scope = set(self._scopes[-1])
        self._scopes.append(scope)
        self._aliases.append(self._aliases[-1].copy())

        for assignment in node.assignments:
            if assignment.local:
                yield from self._enter_assignment(assignment.names)

            yield from self.visit(assignment)

        yield from self.visit(node.node)

        for assignment in reversed(node.assignments):
            if assignment.local:
                yield from self._leave_assignment(assignment.names)

        self._scopes.pop()
        self._aliases.pop()

    def visit_Omit(self, node):
        return self.visit_Condition(node)

    def visit_Condition(self, node):
        target = "__condition"

        def step(expressions, body, condition):
            for i, expression in enumerate(reversed(expressions)):
                stmts = evaluate(expression, body)
                if i > 0:
                    stmts.append(
                        ast.If(
                            ast.Compare(
                                left=load(target),
                                ops=[ast.Is()],
                                comparators=[load(str(condition))]
                            ),
                            body,
                            None
                        )
                    )
                body = stmts
            return body

        def evaluate(node, body=None):
            if isinstance(node, Logical):
                condition = isinstance(node, And)
                return step(node.expressions, body, condition)

            return self._engine(node, target)

        body = evaluate(node.expression)
        orelse = getattr(node, "orelse", None)

        body.append(
            ast.If(
                test=load(target),
                body=self.visit(node.node) or [ast.Pass()],
                orelse=self.visit(orelse) if orelse else None,
            )
        )

        return body

    def visit_Translate(self, node):
        """Translation.

        Visit items and assign output to a default value.

        Finally, compile a translation expression and use either
        result or default.
        """

        body = []

        # Track the blocks of this translation
        self._translations.append(set())

        # Prepare new stream
        append = identifier("append", id(node))
        stream = identifier("stream", id(node))

        body += template("s = new_list", s=stream, new_list=self._new_list) + \
            template("a = s.append", a=append, s=stream)

        # Visit body to generate the message body
        code = self.visit(node.node)
        body.append(TranslationContext(code, append, stream))

        # Reduce white space and assign as message id
        msgid = identifier("msgid", id(node))
        body += template(
            "msgid = __re_whitespace(''.join(stream)).strip()",
            msgid=msgid, stream=stream
        )

        default = msgid

        # Compute translation block mapping if applicable
        names = self._translations[-1]
        if names:
            keys = []
            values = []

            for name in names:
                stream, append = self._get_translation_identifiers(name)
                keys.append(ast.Constant(name))
                values.append(load(stream))

                # Initialize value
                body.insert(
                    0, ast.Assign(
                        targets=[store(stream)],
                        value=ast.Constant("")))

            mapping = ast.Dict(keys=keys, values=values)
        else:
            mapping = None

        # if this translation node has a name, use it as the message id
        if node.msgid:
            msgid = ast.Constant(node.msgid)

        # emit the translation expression
        translation = template(
            "__append(translate("
            "msgid, mapping=mapping, default=default, domain=__i18n_domain, context=__i18n_context, target_language=target_language))",  # noqa:  E501 line too long
            msgid=msgid,
            default=default,
            mapping=mapping)

        if not node.msgid:
            translation = [ast.If(
                test=load(msgid), body=translation, orelse=[]
            )]

        body += translation

        # pop away translation block reference
        self._translations.pop()

        return body

    def visit_Start(self, node):
        try:
            line, column = node.prefix.location
        except AttributeError:
            line, column = 0, 0

        yield Comment(
            " %s%s ... (%d:%d)\n"
            " --------------------------------------------------------" % (
                node.prefix, node.name, line, column))

        if node.attributes:
            yield EmitText(node.prefix + node.name)
            yield from self.visit(node.attributes)

            yield EmitText(node.suffix)
        else:
            yield EmitText(node.prefix + node.name + node.suffix)

    def visit_End(self, node):
        yield EmitText(node.prefix + node.name + node.space + node.suffix)

    def visit_Attribute(self, node):
        attr_format = (node.space + node.name + node.eq +
                       node.quote + "%s" + node.quote)

        filter_args = list(map(self._engine.cache.get, node.filters))

        filter_condition = template(
            "NAME not in CHAIN",
            NAME=ast.Constant(node.name),
            CHAIN=ast.Call(
                func=load("__chain"),
                args=filter_args,
                keywords=[],
            ),
            mode="eval"
        )

        # Static attributes are just outputted directly
        if (
            isinstance(node.expression, ast.Constant)
            and isinstance(node.expression.value, str)
        ):
            s = attr_format % node.expression.value
            if node.filters:
                return template(
                    "if C: __append(S)", C=filter_condition, S=ast.Constant(s)
                )
            else:
                return [EmitText(s)]

        target = identifier("attr", node.name)
        body = self._engine(node.expression, store(target))

        condition = template("TARGET is not None", TARGET=target, mode="eval")

        if node.filters:
            condition = ast.BoolOp(
                values=[condition, filter_condition],
                op=ast.And(),
            )

        return body + template(
            "if CONDITION: __append(FORMAT % TARGET)",
            FORMAT=ast.Constant(attr_format),
            TARGET=target,
            CONDITION=condition,
        )

    def visit_DictAttributes(self, node):
        target = identifier("attr", id(node))
        body = self._engine(node.expression, store(target))

        bool_names = Static(template(
            "set(LIST)", LIST=ast.List(
                elts=[ast.Constant(name) for name in node.bool_names],
                ctx=ast.Load(),
            ), mode="eval"
        ))

        exclude = Static(template(
            "set(LIST)", LIST=ast.List(
                elts=[ast.Constant(name) for name in node.exclude],
                ctx=ast.Load(),
            ), mode="eval"
        ))

        bool_cond = (
            "if name in BOOL_NAMES:\n" +
            indent("if not bool(value): continue\n") +
            indent("value = name\n")
        ) if node.bool_names else ""

        body += template(
            "for name, value in TARGET.items():\n" +
            indent(bool_cond) +
            indent(
                "if name not in EXCLUDE and value is not None:\n" +
                indent(bool_cond) +
                indent(
                    "__append("
                    "' ' + name + '=' + QUOTE + "
                    "QUOTE_FUNC(value, QUOTE, QUOTE_ENTITY, None, None) + "
                    "QUOTE)"
                )
            ),
            TARGET=target,
            EXCLUDE=exclude,
            QUOTE_FUNC="__quote",
            QUOTE=ast.Constant(node.quote),
            QUOTE_ENTITY=ast.Constant(char2entity(node.quote or '\0')),
            BOOL_NAMES=bool_names
        )

        return body

    def visit_Cache(self, node):
        body = []

        for expression in node.expressions:
            # Skip re-evaluation
            if self._expression_cache.get(expression):
                continue

            name = identifier("cache", id(expression))
            target = store(name)

            body += self._engine(expression, target)
            self._expression_cache[expression] = target

        body += self.visit(node.node)

        return body

    def visit_Cancel(self, node):
        body = []

        for expression in node.expressions:
            assert self._expression_cache.get(expression) is not None
            name = identifier("cache", id(expression))
            target = store(name)
            body += self._engine(node.value, target)

        body += self.visit(node.node)

        return body

    def visit_UseInternalMacro(self, node):
        if node.name is None:
            render = "render"
        else:
            render = "render_%s" % mangle(node.name)
        token_reset = template("__token = None")
        return token_reset + template(
            "f(__stream, econtext.copy(), rcontext, "
            "__i18n_domain, __i18n_context, target_language)",
            f=render) + \
            template("econtext.update(rcontext)")

    def visit_DefineSlot(self, node):
        name = "__slot_%s" % mangle(node.name)
        body = self.visit(node.node)

        self._slots.add(name)

        orelse = template(
            "SLOT(__stream, econtext.copy(), rcontext)",
            SLOT=name)
        test = ast.Compare(
            left=load(name),
            ops=[ast.Is()],
            comparators=[load("None")]
        )

        return [
            ast.If(test=test, body=body or [ast.Pass()], orelse=orelse)
        ]

    def visit_Name(self, node):
        """Translation name."""

        if not self._translations:
            raise TranslationError(
                "Not allowed outside of translation.", node.name)

        if node.name in self._translations[-1]:
            raise TranslationError(
                "Duplicate translation name: %s.", node.name)

        self._translations[-1].add(node.name)
        body = []

        # prepare new stream
        stream, append = self._get_translation_identifiers(node.name)
        body += template("s = new_list", s=stream, new_list=self._new_list) + \
            template("a = s.append", a=append, s=stream)

        # generate code
        code = self.visit(node.node)
        body.append(TranslationContext(code, append, stream))

        # output msgid
        text = Text('${%s}' % node.name)
        body += self.visit(text)

        # Concatenate stream
        body += template("stream = ''.join(stream)", stream=stream)

        return body

    def visit_CodeBlock(self, node):
        stmts = template(textwrap.dedent(node.source.strip('\n')))
        stmts = list(map(self._visitor, stmts))
        stmts.insert(0, TokenRef(node.source))
        return stmts

    def visit_UseExternalMacro(self, node):
        self._macros.append(node.extend)

        callbacks = []
        for slot in node.slots:
            key = "__slot_%s" % mangle(slot.name)
            fun = "__fill_%s" % mangle(slot.name)

            self._current_slot.append(slot.name)

            body = self.visit_Context(slot)

            assert self._current_slot.pop() == slot.name

            callbacks.append(
                ast.FunctionDef(
                    name=fun,
                    args=ast.arguments(
                        args=[
                            param("__stream"),
                            param("econtext"),
                            param("rcontext"),
                            param("__i18n_domain"),
                            param("__i18n_context"),
                            param("target_language"),
                        ],
                        defaults=[
                            load("__i18n_domain"),
                            load("__i18n_context"),
                            load("target_language"),
                        ],
                        kwonlyargs=[],
                        posonlyargs=[],
                    ),
                    body=body or [ast.Pass()],
                    decorator_list=[],
                    lineno=None,
                ))

            key = ast.Constant(key)

            assignment = template(
                "_slots = econtext[KEY] = DEQUE((NAME,))",
                KEY=key, NAME=fun, DEQUE=Symbol(collections.deque),
            )

            if node.extend:
                append = template("_slots.appendleft(NAME)", NAME=fun)

                assignment = [ast.Try(
                    body=template("_slots = getname(KEY)", KEY=key),
                    handlers=[ast.ExceptHandler(body=assignment)],
                    finalbody=[],
                    orelse=append,
                )]

            callbacks.extend(assignment)

        assert self._macros.pop() == node.extend

        assignment = self._engine(node.expression, store("__macro"))

        return (
            callbacks +
            assignment +
            [TokenRef(node.expression.value)] +
            template("__m = __macro.include") +
            template(
                "__m(__stream, econtext.copy(), "
                "rcontext, __i18n_domain, __i18n_context, target_language)"
            ) +
            template("econtext.update(rcontext)")
        )

    def visit_Repeat(self, node):
        # Used for loop variable definition and restore
        self._scopes.append(set())

        # Variable assignment and repeat key for single- and
        # multi-variable repeat clause
        if node.local:
            contexts = "econtext",
        else:
            contexts = "econtext", "rcontext"

        for name in node.names:
            if name in COMPILER_INTERNALS_OR_DISALLOWED:
                raise TranslationError(
                    "Name disallowed by compiler.", name
                )

        if len(node.names) > 1:
            targets = [
                ast.Tuple(elts=[
                    subscript(str(name), load(context), ast.Store())
                    for name in node.names], ctx=ast.Store())
                for context in contexts
            ]

            key = ast.Tuple(
                elts=[ast.Constant(name) for name in node.names],
                ctx=ast.Load())
        else:
            name = node.names[0]
            targets = [
                subscript(str(name), load(context), ast.Store())
                for context in contexts
            ]

            key = ast.Constant(node.names[0])

        index = identifier("__index", id(node))
        assignment = [ast.Assign(targets=targets, value=load("__item"))]

        # Make repeat assignment in outer loop
        names = node.names
        local = node.local

        outer = self._engine(node.expression, store("__iterator"))

        if local:
            outer[:] = list(self._enter_assignment(names)) + outer

        outer += template(
            "__iterator, INDEX = getname('repeat')(key, __iterator)",
            key=key, INDEX=index
        )

        # Set a trivial default value for each name assigned to make
        # sure we assign a value even if the iteration is empty
        outer += [ast.Assign(
            targets=[store_econtext(name)
                     for name in node.names],
            value=load("None"))
        ]

        # Compute inner body
        inner = self.visit(node.node)

        # After each iteration, decrease the index
        inner += template("index -= 1", index=index)

        # For items up to N - 1, emit repeat whitespace
        inner += template(
            "if INDEX > 0: __append(WHITESPACE)",
            INDEX=index, WHITESPACE=ast.Constant(node.whitespace)
        )

        # Main repeat loop
        outer += [ast.For(
            target=store("__item"),
            iter=load("__iterator"),
            body=assignment + inner,
            orelse=[],
        )]

        # Finally, clean up assignment if it's local
        if outer:
            outer += self._leave_assignment(names)

        self._scopes.pop()

        return outer

    def _get_translation_identifiers(self, name):
        assert self._translations
        prefix = str(id(self._translations[-1])).replace('-', '_')
        stream = identifier("stream_%s" % prefix, name)
        append = identifier("append_%s" % prefix, name)
        return stream, append

    def _enter_assignment(self, names):
        for name in names:
            yield from template(
                "BACKUP = get(KEY, __marker)",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Constant(str(name)),
            )

    def _leave_assignment(self, names):
        for name in names:
            yield from template(
                "if BACKUP is __marker: del econtext[KEY]\n"
                "else:                 econtext[KEY] = BACKUP",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Constant(str(name)),
            )
