import re
import cgi
import sys
import itertools
import logging
import threading
import functools
import collections
import pickle
import textwrap

from .astutil import load
from .astutil import store
from .astutil import param
from .astutil import swap
from .astutil import subscript
from .astutil import node_annotations
from .astutil import annotated
from .astutil import NameLookupRewriteVisitor
from .astutil import Comment
from .astutil import Symbol
from .astutil import Builtin
from .astutil import Static

from .codegen import TemplateCodeGenerator
from .codegen import template

from .tal import ErrorInfo
from .tal import NAME
from .i18n import simple_translate

from .nodes import Text
from .nodes import Value
from .nodes import Substitution
from .nodes import Assignment
from .nodes import Module
from .nodes import Context

from .tokenize import Token
from .config import DEBUG_MODE
from .exc import TranslationError
from .exc import ExpressionError
from .parser import groupdict

from .utils import DebuggingOutputStream
from .utils import char2entity
from .utils import ListDictProxy
from .utils import native_string
from .utils import byte_string
from .utils import string_type
from .utils import unicode_string
from .utils import version
from .utils import ast
from .utils import safe_native
from .utils import builtins
from .utils import decode_htmlentities


if version >= (3, 0, 0):
    long = int

log = logging.getLogger('chameleon.compiler')

COMPILER_INTERNALS_OR_DISALLOWED = set([
    "econtext",
    "rcontext",
    "str",
    "int",
    "float",
    "long",
    "len",
    "None",
    "True",
    "False",
    "RuntimeError",
    ])


RE_MANGLE = re.compile('[^\w_]')
RE_NAME = re.compile('^%s$' % NAME)

if DEBUG_MODE:
    LIST = template("cls()", cls=DebuggingOutputStream, mode="eval")
else:
    LIST = template("[]", mode="eval")


def identifier(prefix, suffix=None):
    return "__%s_%s" % (prefix, mangle(suffix or id(prefix)))


def mangle(string):
    return RE_MANGLE.sub('_', str(string)).replace('\n', '').replace('-', '_')


def load_econtext(name):
    return template("getitem(KEY)", KEY=ast.Str(s=name), mode="eval")


def store_econtext(name):
    name = native_string(name)
    return subscript(name, load("econtext"), ast.Store())


def store_rcontext(name):
    name = native_string(name)
    return subscript(name, load("rcontext"), ast.Store())


def set_error(token, exception):
    try:
        line, column = token.location
        filename = token.filename
    except AttributeError:
        line, column = 0, 0
        filename = "<string>"

    string = safe_native(token)

    return template(
        "rcontext.setdefault('__error__', [])."
        "append((string, line, col, src, exc))",
        string=ast.Str(s=string),
        line=ast.Num(n=line),
        col=ast.Num(n=column),
        src=ast.Str(s=filename),
        sys=Symbol(sys),
        exc=exception,
        )


def try_except_wrap(stmts, token):
    exception = template(
        "exc_info()[1]", exc_info=Symbol(sys.exc_info), mode="eval"
        )

    body = set_error(token, exception) + template("raise")

    return ast.TryExcept(
        body=stmts,
        handlers=[ast.ExceptHandler(body=body)],
        )


@template
def emit_node(node):  # pragma: no cover
    __append(node)


@template
def emit_node_if_non_trivial(node):  # pragma: no cover
    if node is not None:
        __append(node)


@template
def emit_bool(target, s, default_marker=None,
                 default=None):  # pragma: no cover
    if target is default_marker:
        target = default
    elif target:
        target = s
    else:
        target = None


@template
def emit_convert(
    target, encoded=byte_string, str=unicode_string,
    long=long, type=type,
    default_marker=None, default=None):  # pragma: no cover
    if target is None:
        pass
    elif target is default_marker:
        target = default
    else:
        __tt = type(target)

        if __tt is int or __tt is float or __tt is long:
            target = str(target)
        elif __tt is encoded:
            target = decode(target)
        elif __tt is not str:
            try:
                target = target.__html__
            except AttributeError:
                __converted = convert(target)
                target = str(target) if target is __converted else __converted
            else:
                target = target()


@template
def emit_func_convert(
    func, encoded=byte_string, str=unicode_string,
    long=long, type=type):  # pragma: no cover
    def func(target):
        if target is None:
            return

        __tt = type(target)

        if __tt is int or __tt is float or __tt is long:
            target = str(target)

        elif __tt is encoded:
            target = decode(target)

        elif __tt is not str:
            try:
                target = target.__html__
            except AttributeError:
                __converted = convert(target)
                target = str(target) if target is __converted else __converted
            else:
                target = target()

        return target


@template
def emit_translate(target, msgid, default=None):  # pragma: no cover
    target = translate(msgid, default=default, domain=__i18n_domain, context=__i18n_context)


@template
def emit_func_convert_and_escape(
    func, str=unicode_string, long=long,
    type=type, encoded=byte_string):  # pragma: no cover

    def func(target, quote, quote_entity, default, default_marker):
        if target is None:
            return

        if target is default_marker:
            return default

        __tt = type(target)

        if __tt is int or __tt is float or __tt is long:
            target = str(target)
        else:
            if __tt is encoded:
                target = decode(target)
            elif __tt is not str:
                try:
                    target = target.__html__
                except:
                    __converted = convert(target)
                    target = str(target) if target is __converted \
                             else __converted
                else:
                    return target()

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

        return target


class Interpolator(object):
    braces_required_regex = re.compile(
        r'(?<!\\)\$({(?P<expression>.*)})',
        re.DOTALL)

    braces_optional_regex = re.compile(
        r'(?<!\\)\$({(?P<expression>.*)}|(?P<variable>[A-Za-z][A-Za-z0-9_]*))',
        re.DOTALL)

    def __init__(self, expression, braces_required, translate=False):
        self.expression = expression
        self.regex = self.braces_required_regex if braces_required else \
                     self.braces_optional_regex
        self.translate = translate

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
                nodes.append(ast.Str(s=text))
                break

            part = text[:m.start()]
            text = text[m.start():]

            if part:
                node = ast.Str(s=part)
                nodes.append(node)

            if not body:
                target = name
            else:
                target = store("%s_%d" % (name.id, text.pos))

            while True:
                d = groupdict(m, matched)
                string = d["expression"] or d.get("variable") or ""
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
                    assign = ast.Assign(targets=[target], value=ast.Str(s=s))
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

            if translate and isinstance(target, ast.Str):
                target = template(
                    "translate(msgid, domain=__i18n_domain, context=__i18n_context)",
                    msgid=target, mode="eval",
                    )
        else:
            if translate:
                formatting_string = ""
                keys = []
                values = []

                for node in nodes:
                    if isinstance(node, ast.Str):
                        formatting_string += node.s
                    else:
                        string = expr_map[node]
                        formatting_string += "${%s}" % string
                        keys.append(ast.Str(s=string))
                        values.append(node)

                target = template(
                    "translate(msgid, mapping=mapping, domain=__i18n_domain, context=__i18n_context)",
                    msgid=ast.Str(s=formatting_string),
                    mapping=ast.Dict(keys=keys, values=values),
                    mode="eval"
                    )
            else:
                nodes = [
                    template(
                        "NODE if NODE is not None else ''",
                        NODE=node, mode="eval"
                        )
                    for node in nodes
                    ]

                target = ast.BinOp(
                    left=ast.Str(s="%s" * len(nodes)),
                    op=ast.Mod(),
                    right=ast.Tuple(elts=nodes, ctx=ast.Load()))

        body += [ast.Assign(targets=[name], value=target)]
        return body


class ExpressionEngine(object):
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

    >>> eval('string:test ${1}${2}')
    'test 12'

    """

    supported_char_escape_set = set(('&', '<', '>'))

    def __init__(self, parser, char_escape=(),
                 default=None, default_marker=None):
        self._parser = parser
        self._char_escape = char_escape
        self._default = default
        self._default_marker = default_marker

    def __call__(self, string, target):
        # BBB: This method is deprecated. Instead, a call should first
        # be made to ``parse`` and then one of the assignment methods
        # ("value" or "text").

        compiler = self.parse(string)
        return compiler(string, target)

    def parse(self, string):
        expression = self._parser(string)
        compiler = self.get_compiler(expression, string)
        return ExpressionCompiler(compiler, self)

    def get_compiler(self, expression, string):
        def compiler(target, engine, result_type=None, *args):
            stmts = expression(target, engine)

            if result_type is not None:
                method = getattr(self, '_convert_%s' % result_type)
                steps = method(target, *args)
                stmts.extend(steps)

            return [try_except_wrap(stmts, string)]

        return compiler

    def _convert_bool(self, target, s):
        """Converts value given by ``target`` to a string ``s`` if the
        target is a true value, otherwise ``None``.
        """

        return emit_bool(
            target, ast.Str(s=s),
            default=self._default,
            default_marker=self._default_marker
            )

    def _convert_text(self, target):
        """Converts value given by ``target`` to text."""

        if self._char_escape:
            # This is a cop-out - we really only support a very select
            # set of escape characters
            other = set(self._char_escape) - self.supported_char_escape_set

            if other:
                for supported in '"', '\'', '':
                    if supported in self._char_escape:
                        quote = supported
                        break
                else:
                    raise RuntimeError(
                        "Unsupported escape set: %s." % repr(self._char_escape)
                        )
            else:
                quote = '\0'

            entity = char2entity(quote or '\0')

            return template(
                "TARGET = __quote(TARGET, QUOTE, Q_ENTITY, DEFAULT, MARKER)",
                TARGET=target,
                QUOTE=ast.Str(s=quote),
                Q_ENTITY=ast.Str(s=entity),
                DEFAULT=self._default,
                MARKER=self._default_marker,
                )

        return emit_convert(
            target,
            default=self._default,
            default_marker=self._default_marker,
            )


class ExpressionCompiler(object):
    def __init__(self, compiler, engine):
        self.compiler = compiler
        self.engine = engine

    def assign_bool(self, target, s):
        return self.compiler(target, self.engine, "bool", s)

    def assign_text(self, target):
        return self.compiler(target, self.engine, "text")

    def assign_value(self, target):
        return self.compiler(target, self.engine)


class ExpressionEvaluator(object):
    """Evaluates dynamic expression.

    This is not particularly efficient, but supported for legacy
    applications.

    >>> from chameleon import tales
    >>> parser = tales.ExpressionParser({'python': tales.PythonExpr}, 'python')
    >>> engine = functools.partial(ExpressionEngine, parser)

    >>> evaluate = ExpressionEvaluator(engine, {
    ...     'foo': 'bar',
    ...     })

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

        expression = "%s:%s" % (expression_type, string)

        try:
            evaluate = self._cache[expression]
        except KeyError:
            assignment = Assignment(["_result"], expression, True)
            module = Module("evaluate", Context(assignment))

            compiler = Compiler(
                self._engine, module, ('econtext', 'rcontext') + self._names
                )

            env = {}
            exec(compiler.code, env)
            evaluate = self._cache[expression] = env["evaluate"]

        evaluate(econtext, rcontext, *self._builtins)
        return econtext['_result']


class NameTransform(object):
    """
    >>> nt = NameTransform(
    ...     set(('foo', 'bar', )), {'boo': 'boz'},
    ...     ('econtext', ),
    ... )

    >>> def test(node):
    ...     rewritten = nt(node)
    ...     module = ast.Module([ast.fix_missing_locations(rewritten)])
    ...     codegen = TemplateCodeGenerator(module)
    ...     return codegen.code

    Any odd name:

    >>> test(load('frobnitz'))
    "getitem('frobnitz')"

    A 'builtin' name will first be looked up via ``get`` allowing fall
    back to the global builtin value:

    >>> test(load('foo'))
    "get('foo', foo)"

    Internal names (with two leading underscores) are left alone:

    >>> test(load('__internal'))
    '__internal'

    Compiler internals or disallowed names:

    >>> test(load('econtext'))
    'econtext'

    Aliased names:

    >>> test(load('boo'))
    'boz'

    """

    def __init__(self, builtins, aliases, internals):
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
                key=ast.Str(s=name),
                name=load(name),
                )

        # Otherwise, simply acquire it from the dynamic context.
        return load_econtext(name)


class ExpressionTransform(object):
    """Internal wrapper to transform expression nodes into assignment
    statements.

    The node input may use the provided expression engine, but other
    expression node types are supported such as ``Builtin`` which
    simply resolves a built-in name.

    Used internally be the compiler.
    """

    loads_symbol = Symbol(pickle.loads)

    def __init__(self, engine_factory, cache, visitor, strict=True):
        self.engine_factory = engine_factory
        self.cache = cache
        self.strict = strict
        self.visitor = visitor

    def __call__(self, expression, target):
        if isinstance(target, string_type):
            target = store(target)

        try:
            stmts = self.translate(expression, target)
        except ExpressionError:
            if self.strict:
                raise

            exc = sys.exc_info()[1]
            p = pickle.dumps(exc, -1)

            stmts = template(
                "__exc = loads(p)", loads=self.loads_symbol, p=ast.Str(s=p)
                )

            token = Token(exc.token, exc.offset, filename=exc.filename)

            stmts += set_error(token, load("__exc"))
            stmts += [ast.Raise(exc=load("__exc"))]

        # Apply visitor to each statement
        for stmt in stmts:
            self.visitor(stmt)

        return stmts

    def translate(self, expression, target):
        if isinstance(target, string_type):
            target = store(target)

        cached = self.cache.get(expression)

        if cached is not None:
            stmts = [ast.Assign(targets=[target], value=cached)]
        elif isinstance(expression, ast.expr):
            stmts = [ast.Assign(targets=[target], value=expression)]
        else:
            # The engine interface supports simple strings, which
            # default to expression nodes
            if isinstance(expression, string_type):
                expression = Value(expression, True)

            kind = type(expression).__name__
            visitor = getattr(self, "visit_%s" % kind)
            stmts = visitor(expression, target)

            # Add comment
            target_id = getattr(target, "id", target)
            comment = Comment(" %r -> %s" % (expression, target_id))
            stmts.insert(0, comment)

        return stmts

    def visit_Value(self, node, target):
        engine = self.engine_factory()
        compiler = engine.parse(node.value)
        return compiler.assign_value(target)

    def visit_Copy(self, node, target):
        return self.translate(node.expression, target)

    def visit_Default(self, node, target):
        value = annotated(node.marker)
        return [ast.Assign(targets=[target], value=value)]

    def visit_Substitution(self, node, target):
        engine = self.engine_factory(
            char_escape=node.char_escape,
            default=node.default,
            )
        compiler = engine.parse(node.value)
        return compiler.assign_text(target)

    def visit_Negate(self, node, target):
        return self.translate(node.value, target) + \
               template("TARGET = not TARGET", TARGET=target)

    def visit_Identity(self, node, target):
        expression = self.translate(node.expression, "__expression")
        value = self.translate(node.value, "__value")

        return expression + value + \
               template("TARGET = __expression is __value", TARGET=target)

    def visit_Equality(self, node, target):
        expression = self.translate(node.expression, "__expression")
        value = self.translate(node.value, "__value")

        return expression + value + \
               template("TARGET = __expression == __value", TARGET=target)

    def visit_Boolean(self, node, target):
        engine = self.engine_factory()
        compiler = engine.parse(node.value)
        return compiler.assign_bool(target, node.s)

    def visit_Interpolation(self, node, target):
        expr = node.value
        if isinstance(expr, Substitution):
            engine = self.engine_factory(
                char_escape=expr.char_escape,
                default=expr.default,
                )
        elif isinstance(expr, Value):
            engine = self.engine_factory()
        else:
            raise RuntimeError("Bad value: %r." % node.value)

        interpolator = Interpolator(
            expr.value, node.braces_required, node.translation
            )

        compiler = engine.get_compiler(interpolator, expr.value)
        return compiler(target, engine)

    def visit_Translate(self, node, target):
        if node.msgid is not None:
            msgid = ast.Str(s=node.msgid)
        else:
            msgid = target
        return self.translate(node.node, target) + \
               emit_translate(target, msgid, default=target)

    def visit_Static(self, node, target):
        value = annotated(node)
        return [ast.Assign(targets=[target], value=value)]

    def visit_Builtin(self, node, target):
        value = annotated(node)
        return [ast.Assign(targets=[target], value=value)]


class Compiler(object):
    """Generic compiler class.

    Iterates through nodes and yields Python statements which form a
    template program.
    """

    exceptions = NameError, \
                 ValueError, \
                 AttributeError, \
                 LookupError, \
                 TypeError

    defaults = {
        'translate': Symbol(simple_translate),
        'decode': Builtin("str"),
        'convert': Builtin("str"),
        }

    lock = threading.Lock()

    global_builtins = set(builtins.__dict__)

    def __init__(self, engine_factory, node, builtins={}, strict=True):
        self._scopes = [set()]
        self._expression_cache = {}
        self._translations = []
        self._builtins = builtins
        self._aliases = [{}]
        self._macros = []
        self._current_slot = []

        internals = COMPILER_INTERNALS_OR_DISALLOWED | \
                    set(self.defaults)

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

        if isinstance(node_annotations, dict):
            self.lock.acquire()
            backup = node_annotations.copy()
        else:
            backup = None

        try:
            module = ast.Module([])
            module.body += self.visit(node)
            ast.fix_missing_locations(module)
            generator = TemplateCodeGenerator(module)
        finally:
            if backup is not None:
                node_annotations.clear()
                node_annotations.update(backup)
                self.lock.release()

        self.code = generator.code

    def visit(self, node):
        if node is None:
            return ()
        kind = type(node).__name__
        visitor = getattr(self, "visit_%s" % kind)
        iterator = visitor(node)
        return list(iterator)

    def visit_Sequence(self, node):
        for item in node.items:
            for stmt in self.visit(item):
                yield stmt

    def visit_Element(self, node):
        for stmt in self.visit(node.start):
            yield stmt

        for stmt in self.visit(node.content):
            yield stmt

        if node.end is not None:
            for stmt in self.visit(node.end):
                yield stmt

    def visit_Module(self, node):
        body = []

        body += template("import re")
        body += template("import functools")
        body += template("from itertools import chain as __chain")
        body += template("__marker = object()")
        body += template(
            r"g_re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)')"
        )
        body += template(
            r"g_re_needs_escape = re.compile(r'[&<>\"\']').search")

        body += template(
            r"__re_whitespace = "
            r"functools.partial(re.compile('\s+').sub, ' ')",
        )

        # Visit module content
        program = self.visit(node.program)

        body += [ast.FunctionDef(
            name=node.name, args=ast.arguments(
                args=[param(b) for b in self._builtins],
                defaults=(),
                ),
            body=program
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
            keys=[ast.Str(s=name) for name in names],
            values=[load(name) for name in names],
            ))]

        return functions

    def visit_Context(self, node):
        return template("getitem = econtext.__getitem__") + \
               template("get = econtext.get") + \
               self.visit(node.node)

    def visit_Macro(self, node):
        body = []

        # Initialization
        body += template("__append = __stream.append")
        body += template("__re_amp = g_re_amp")
        body += template("__re_needs_escape = g_re_needs_escape")

        body += emit_func_convert("__convert")
        body += emit_func_convert_and_escape("__quote")

        # Resolve defaults
        for name in self.defaults:
            body += template(
                "NAME = econtext[KEY]",
                NAME=name, KEY=ast.Str(s="__" + name)
            )

        # Internal set of defined slots
        self._slots = set()

        # Visit macro body
        nodes = itertools.chain(*tuple(map(self.visit, node.body)))

        # Slot resolution
        for name in self._slots:
            body += template(
                "try: NAME = econtext[KEY].pop()\n"
                "except: NAME = None",
                KEY=ast.Str(s=name), NAME=store(name))

        # Append visited nodes
        body += nodes

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
                    ],
                defaults=[load("None"), load("None")],
            ),
            body=body
            )

        yield function

    def visit_Text(self, node):
        return emit_node(ast.Str(s=node.value))

    def visit_Domain(self, node):
        backup = "__previous_i18n_domain_%s" % mangle(id(node))
        return template("BACKUP = __i18n_domain", BACKUP=backup) + \
               template("__i18n_domain = NAME", NAME=ast.Str(s=node.name)) + \
               self.visit(node.node) + \
               template("__i18n_domain = BACKUP", BACKUP=backup)

    def visit_TxContext(self, node):
        backup = "__previous_i18n_context_%s" % mangle(id(node))
        return template("BACKUP = __i18n_context", BACKUP=backup) + \
               template("__i18n_context = NAME", NAME=ast.Str(s=node.name)) + \
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
            "econtext[key] = cls(__exc, rcontext['__error__'][-1][1:3])",
            cls=ErrorInfo,
            key=ast.Str(s=node.name),
            )

        body += [ast.TryExcept(
            body=self.visit(node.node),
            handlers=[ast.ExceptHandler(
                type=ast.Tuple(elts=[Builtin("Exception")], ctx=ast.Load()),
                name=store("__exc"),
                body=(error_assignment + \
                      template("del __stream[fallback:]", fallback=fallback) + \
                      fallback_body
                      ),
                )]
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
                    "rcontext[KEY] = __value", KEY=ast.Str(s=native_string(name))
                    )

        return assignment

    def visit_Define(self, node):
        scope = set(self._scopes[-1])
        self._scopes.append(scope)
        self._aliases.append(self._aliases[-1].copy())

        for assignment in node.assignments:
            if assignment.local:
                for stmt in self._enter_assignment(assignment.names):
                    yield stmt

            for stmt in self.visit(assignment):
                yield stmt

        for stmt in self.visit(node.node):
            yield stmt

        for assignment in node.assignments:
            if assignment.local:
                for stmt in self._leave_assignment(assignment.names):
                    yield stmt

        self._scopes.pop()
        self._aliases.pop()

    def visit_Omit(self, node):
        return self.visit_Condition(node)

    def visit_Condition(self, node):
        target = "__condition"
        assignment = self._engine(node.expression, target)

        assert assignment

        for stmt in assignment:
            yield stmt

        body = self.visit(node.node) or [ast.Pass()]

        orelse = getattr(node, "orelse", None)
        if orelse is not None:
            orelse = self.visit(orelse)

        test = load(target)

        yield ast.If(test=test, body=body, orelse=orelse)

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
        body += template("s = new_list", s=stream, new_list=LIST) + \
                template("a = s.append", a=append, s=stream)

        # Visit body to generate the message body
        code = self.visit(node.node)
        swap(ast.Suite(body=code), load(append), "__append")
        body += code

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
                keys.append(ast.Str(s=name))
                values.append(load(stream))

                # Initialize value
                body.insert(
                    0, ast.Assign(
                        targets=[store(stream)],
                        value=ast.Str(s=native_string(""))))

            mapping = ast.Dict(keys=keys, values=values)
        else:
            mapping = None

        # if this translation node has a name, use it as the message id
        if node.msgid:
            msgid = ast.Str(s=node.msgid)

        # emit the translation expression
        body += template(
            "if msgid: __append(translate("
            "msgid, mapping=mapping, default=default, domain=__i18n_domain, context=__i18n_context))",
            msgid=msgid, default=default, mapping=mapping
            )

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
            for stmt in emit_node(ast.Str(s=node.prefix + node.name)):
                yield stmt

            for stmt in self.visit(node.attributes):
                yield stmt

            for stmt in emit_node(ast.Str(s=node.suffix)):
                yield stmt
        else:
            for stmt in emit_node(
                ast.Str(s=node.prefix + node.name + node.suffix)):
                yield stmt

    def visit_End(self, node):
        for stmt in emit_node(ast.Str(
            s=node.prefix + node.name + node.space + node.suffix)):
            yield stmt

    def visit_Attribute(self, node):
        attr_format = (node.space + node.name + node.eq +
                       node.quote + "%s" + node.quote)

        filter_args = list(map(self._engine.cache.get, node.filters))

        filter_condition = template(
            "NAME not in CHAIN",
            NAME=ast.Str(s=node.name),
            CHAIN=ast.Call(
                func=load("__chain"),
                args=filter_args,
                keywords=[],
                starargs=None,
                kwargs=None,
            ),
            mode="eval"
        )

        # Static attributes are just outputted directly
        if isinstance(node.expression, ast.Str):
            s = attr_format % node.expression.s
            if node.filters:
                return template(
                    "if C: __append(S)", C=filter_condition, S=ast.Str(s=s)
                )
            else:
                return template("__append(S)", S=ast.Str(s=s))

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
            FORMAT=ast.Str(s=attr_format),
            TARGET=target,
            CONDITION=condition,
        )

    def visit_DictAttributes(self, node):
        target = identifier("attr", id(node))
        body = self._engine(node.expression, store(target))

        exclude = Static(template(
            "set(LIST)", LIST=ast.List(
                elts=[ast.Str(s=name) for name in node.exclude],
                ctx=ast.Load(),
            ), mode="eval"
        ))

        body += template(
            "for name, value in TARGET.items():\n  "
            "if name not in EXCLUDE and value is not None: __append("
            "' ' + name + '=' + QUOTE + "
            "QUOTE_FUNC(value, QUOTE, QUOTE_ENTITY, None, None) + QUOTE"
            ")",
            TARGET=target,
            EXCLUDE=exclude,
            QUOTE_FUNC="__quote",
            QUOTE=ast.Str(s=node.quote),
            QUOTE_ENTITY=ast.Str(s=char2entity(node.quote or '\0')),
            )

        return body

    def visit_Cache(self, node):
        body = []

        for expression in node.expressions:
            name = identifier("cache", id(expression))
            target = store(name)

            # Skip re-evaluation
            if self._expression_cache.get(expression):
                continue

            body += self._engine(expression, target)
            self._expression_cache[expression] = target

        body += self.visit(node.node)

        return body

    def visit_Cancel(self, node):
        body = []

        for expression in node.expressions:
            name = identifier("cache", id(expression))
            target = store(name)

            if not self._expression_cache.get(expression):
               continue

            body.append(ast.Assign([target], load("None")))

        body += self.visit(node.node)

        return body

    def visit_UseInternalMacro(self, node):
        if node.name is None:
            render = "render"
        else:
            render = "render_%s" % mangle(node.name)

        return template(
            "f(__stream, econtext.copy(), rcontext, __i18n_domain)",
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
        body += template("s = new_list", s=stream, new_list=LIST) + \
                template("a = s.append", a=append, s=stream)

        # generate code
        code = self.visit(node.node)
        swap(ast.Suite(body=code), load(append), "__append")
        body += code

        # output msgid
        text = Text('${%s}' % node.name)
        body += self.visit(text)

        # Concatenate stream
        body += template("stream = ''.join(stream)", stream=stream)

        return body

    def visit_CodeBlock(self, node):
        stmts = template(textwrap.dedent(node.source.strip('\n')))

        for stmt in stmts:
            self._visitor(stmt)

        return [try_except_wrap(stmts, node.source)]

    def visit_UseExternalMacro(self, node):
        self._macros.append(node.extend)

        callbacks = []
        for slot in node.slots:
            key = "__slot_%s" % mangle(slot.name)
            fun = "__fill_%s" % mangle(slot.name)

            self._current_slot.append(slot.name)

            body = template("getitem = econtext.__getitem__") + \
                   template("get = econtext.get") + \
                   self.visit(slot.node)

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
                            ],
                        defaults=[load("__i18n_domain"), load("__i18n_context")],
                        ),
                    body=body or [ast.Pass()],
                ))

            key = ast.Str(s=key)

            assignment = template(
                "_slots = econtext[KEY] = DEQUE((NAME,))",
                KEY=key, NAME=fun, DEQUE=Symbol(collections.deque),
                )

            if node.extend:
                append = template("_slots.appendleft(NAME)", NAME=fun)

                assignment = [ast.TryExcept(
                    body=template("_slots = getitem(KEY)", KEY=key),
                    handlers=[ast.ExceptHandler(body=assignment)],
                    orelse=append,
                    )]

            callbacks.extend(assignment)

        assert self._macros.pop() == node.extend

        assignment = self._engine(node.expression, store("__macro"))

        return (
            callbacks + \
            assignment + \
            template(
                "__macro.include(__stream, econtext.copy(), " \
                "rcontext, __i18n_domain)") + \
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
                    subscript(native_string(name), load(context), ast.Store())
                    for name in node.names], ctx=ast.Store())
                for context in contexts
                ]

            key = ast.Tuple(
                elts=[ast.Str(s=name) for name in node.names],
                ctx=ast.Load())
        else:
            name = node.names[0]
            targets = [
                subscript(native_string(name), load(context), ast.Store())
                for context in contexts
                ]

            key = ast.Str(s=node.names[0])

        index = identifier("__index", id(node))
        assignment = [ast.Assign(targets=targets, value=load("__item"))]

        # Make repeat assignment in outer loop
        names = node.names
        local = node.local

        outer = self._engine(node.expression, store("__iterator"))

        if local:
            outer[:] = list(self._enter_assignment(names)) + outer

        outer += template(
            "__iterator, INDEX = getitem('repeat')(key, __iterator)",
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
            INDEX=index, WHITESPACE=ast.Str(s=node.whitespace)
            )

        # Main repeat loop
        outer += [ast.For(
            target=store("__item"),
            iter=load("__iterator"),
            body=assignment + inner,
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
            for stmt in template(
                "BACKUP = get(KEY, __marker)",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=native_string(name)),
                ):
                yield stmt

    def _leave_assignment(self, names):
        for name in names:
            for stmt in template(
                "if BACKUP is __marker: del econtext[KEY]\n"
                "else:                 econtext[KEY] = BACKUP",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=native_string(name)),
                ):
                yield stmt
