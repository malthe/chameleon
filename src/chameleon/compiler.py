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
from ast import Try

from .astutil import Builtin
from .astutil import Comment
from .astutil import NameLookupRewriteVisitor
from .astutil import Node
from .astutil import Static
from .astutil import Symbol
from .astutil import TokenRef
from .astutil import annotated
from .astutil import load
from .astutil import node_annotations
from .astutil import param
from .astutil import store
from .astutil import subscript
from .astutil import swap
from .codegen import TemplateCodeGenerator
from .codegen import template
from .config import DEBUG_MODE
from .exc import ExpressionError
from .exc import TranslationError
from .i18n import simple_translate
from .nodes import And
from .nodes import Assignment
from .nodes import Context
from .nodes import Equals
from .nodes import Is
from .nodes import IsNot
from .nodes import Logical
from .nodes import Module
from .nodes import Substitution
from .nodes import Text
from .nodes import Value
from .parser import groupdict
from .tal import NAME
from .tal import ErrorInfo
from .tokenize import Token
from .utils import DebuggingOutputStream
from .utils import ListDictProxy
from .utils import char2entity
from .utils import decode_htmlentities
from .utils import join
from .utils import safe_native


long = int

log = logging.getLogger('chameleon.compiler')

COMPILER_INTERNALS_OR_DISALLOWED = {
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
}


RE_MANGLE = re.compile(r'[^\w_]')
RE_NAME = re.compile('^%s$' % NAME)

if DEBUG_MODE:
    LIST = template("cls()", cls=DebuggingOutputStream, mode="eval")
else:
    LIST = template("[]", mode="eval")


def identifier(prefix, suffix=None):
    return "__{}_{}".format(prefix, mangle(suffix or id(prefix)))


def mangle(string):
    return RE_MANGLE.sub(
        '_', str(string)
    ).replace('\n', '').replace('-', '_')


def load_econtext(name):
    return template("getname(KEY)", KEY=ast.Str(s=name), mode="eval")


def store_econtext(name):
    name = str(name)
    return subscript(name, load("econtext"), ast.Store())


def store_rcontext(name):
    name = str(name)
    return subscript(name, load("rcontext"), ast.Store())


def set_token(stmts, token):
    pos = getattr(token, "pos", 0)
    body = template("__token = pos", pos=TokenRef(pos, len(token)))
    return body + stmts


def eval_token(token):
    try:
        line, column = token.location
    except AttributeError:
        line, column = 0, 0

    string = safe_native(token)

    return template(
        "(string, line, col)",
        string=ast.Str(s=string),
        line=ast.Num(n=line),
        col=ast.Num(n=column),
        mode="eval"
    )


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
                        func_args=('target', 'encoded', 'str', 'long', 'type',
                                   'default_marker', 'default'),
                        func_defaults=(bytes, str, long, type, None),
                        source=r"""
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
                target = target()""")


emit_func_convert = template(
    is_func=True, func_args=(
        'func', 'encoded', 'str', 'long', 'type'), func_defaults=(
            bytes, str, long, type), source=r"""
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

        return target""")


emit_translate = template(is_func=True,
                          func_args=('target', 'msgid', 'target_language',
                                     'default'),
                          func_defaults=(None,),
                          source=r"""
    target = translate(msgid, default=default, domain=__i18n_domain,
                       context=__i18n_context,
                       target_language=target_language)""")


emit_func_convert_and_escape = template(
    is_func=True,
    func_args=('func', 'str', 'long', 'type', 'encoded'),
    func_defaults=(str, long, type, bytes,),
    source=r"""
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

        return target""")


class EmitText(Node):
    """Append text to output."""

    _fields = "s",


class Scope(Node):
    """"Set a local output scope."""

    _fields = "body", "append", "stream"

    body = None
    append = None
    stream = None


class Interpolator:
    braces_required_regex = re.compile(
        r'(\$)?\$({(?P<expression>.*)})',
        re.DOTALL)

    braces_optional_regex = re.compile(
        r'(\$)?\$({(?P<expression>.*)}|(?P<variable>[A-Za-z][A-Za-z0-9_]*))',
        re.DOTALL)

    def __init__(self, expression, braces_required, translate=False,
                 decode_htmlentities=False):
        self.expression = expression
        self.regex = self.braces_required_regex if braces_required else \
            self.braces_optional_regex
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
                nodes.append(ast.Str(s=text))
                break

            part = text[:m.start()]
            text = text[m.start():]

            skip = text.startswith('$$')
            if skip:
                part = part + '$'

            if part:
                part = part.replace('$$', '$')
                node = ast.Str(s=part)
                nodes.append(node)

            if skip:
                text = text[2:]
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
                    "translate(msgid, domain=__i18n_domain, context=__i18n_context, target_language=target_language)",  # noqa:  E501 line too long
                    msgid=target,
                    mode="eval",
                    target_language=load("target_language"),
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
                    "translate(msgid, mapping=mapping, domain=__i18n_domain, context=__i18n_context, target_language=target_language)",   # noqa:  E501 line too long
                    msgid=ast.Str(
                        s=formatting_string),
                    target_language=load("target_language"),
                    mapping=ast.Dict(
                        keys=keys,
                        values=values),
                    mode="eval")
            else:
                nodes = [
                    node if isinstance(node, ast.Str) else
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

    def parse(self, string, handle_errors=True, char_escape=None):
        expression = self._parser(string)
        compiler = self.get_compiler(
            expression, string, handle_errors, char_escape)
        return ExpressionCompiler(compiler, self)

    def get_compiler(self, expression, string, handle_errors, char_escape):
        if char_escape is None:
            char_escape = self._char_escape

        def compiler(target, engine, result_type=None, *args):
            stmts = expression(target, engine)

            if result_type is not None:
                method = getattr(self, '_convert_%s' % result_type)
                steps = method(target, char_escape, *args)
                stmts.extend(steps)

            if handle_errors:
                return set_token(stmts, string.strip())

            return stmts

        return compiler

    def _convert_bool(self, target, char_escape, s):
        """Converts value given by ``target`` to a string ``s`` if the
        target is a true value, otherwise ``None``.
        """

        return emit_bool(
            target, ast.Str(s=s),
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
            QUOTE=ast.Str(s=quote),
            Q_ENTITY=ast.Str(s=entity),
            DEFAULT=self._default,
            MARKER=self._default_marker,
        )


class ExpressionCompiler:
    def __init__(self, compiler, engine):
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

    >>> def test(node):
    ...     rewritten = nt(node)
    ...     module = ast.Module([ast.fix_missing_locations(rewritten)])
    ...     codegen = TemplateCodeGenerator(module)
    ...     return codegen.code

    Any odd name:

    >>> test(load('frobnitz'))
    "getname('frobnitz')"

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


class ExpressionTransform:
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
        if isinstance(target, str):
            target = store(target)

        try:
            stmts = self.translate(expression, target)
        except ExpressionError as exc:
            if self.strict:
                raise

            p = pickle.dumps(exc, -1)

            stmts = template(
                "__exc = loads(p)", loads=self.loads_symbol, p=ast.Str(s=p)
            )

            stmts += set_token([ast.Raise(exc=load("__exc"))], exc.token)

        # Apply visitor to each statement
        for stmt in stmts:
            self.visitor(stmt)

        return stmts

    def translate(self, expression, target):
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
        return self.translate(node.expression, target)

    def visit_Substitution(self, node, target):
        engine = self.engine_factory(
            default=node.default,
            default_marker=node.default_marker
        )
        compiler = engine.parse(node.value, char_escape=node.char_escape)
        return compiler.assign_text(target)

    def visit_Negate(self, node, target):
        return self.translate(node.value, target) + \
            template("TARGET = not TARGET", TARGET=target)

    def visit_BinOp(self, node, target):
        expression = self.translate(node.left, "__expression")
        value = self.translate(node.right, "__value")

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
                default_marker=expr.default_marker
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

        compiler = engine.get_compiler(
            interpolator, expr.value, True, ()
        )
        return compiler(target, engine, "text")

    def visit_Translate(self, node, target):
        if node.msgid is not None:
            msgid = ast.Str(s=node.msgid)
        else:
            msgid = target
        return self.translate(node.node, target) + \
            emit_translate(
            target, msgid, "target_language",
            default=target
        )

    def visit_Static(self, node, target):
        value = annotated(node)
        return [ast.Assign(targets=[target], value=value)]

    def visit_Builtin(self, node, target):
        value = annotated(node)
        return [ast.Assign(targets=[target], value=value)]

    def visit_Symbol(self, node, target):
        annotated(node)
        return template("TARGET = SYMBOL", TARGET=target, SYMBOL=node)


class Compiler:
    """Generic compiler class.

    Iterates through nodes and yields Python statements which form a
    template program.
    """

    defaults = {
        'translate': Symbol(simple_translate),
        'decode': Builtin("str"),
        'convert': Builtin("str"),
        'on_error_handler': Builtin("str")
    }

    lock = threading.Lock()

    global_builtins = set(builtins.__dict__)

    def __init__(self, engine_factory, node, filename, source,
                 builtins={}, strict=True):
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

            class Generator(TemplateCodeGenerator):
                scopes = [Scope()]

                def visit_EmitText(self, node):
                    append = load(self.scopes[-1].append or "__append")
                    for node in template(
                        "append(s)", append=append, s=ast.Str(
                            s=node.s)):
                        self.visit(node)

                def visit_Scope(self, node):
                    self.scopes.append(node)
                    body = list(node.body)
                    swap(body, load(node.append), "__append")
                    if node.stream:
                        swap(body, load(node.stream), "__stream")
                    for node in body:
                        self.visit(node)
                    self.scopes.pop()

            generator = Generator(module, source)
            tokens = [
                Token(source[pos:pos + length], pos, source)
                for pos, length in generator.tokens
            ]
            token_map_def = "__tokens = {" + ", ".join("%d: %r" % (
                token.pos,
                (token, ) + token.location
            ) for token in tokens) + "}"
        finally:
            if backup is not None:
                node_annotations.clear()
                node_annotations.update(backup)
                self.lock.release()

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
            r"g_re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)')"
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
            Try(
                body=nodes,
                handlers=[ast.ExceptHandler(body=exc_handler)]
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
                ],
                defaults=[load("None"), load("None")],
            ),
            body=body
        )

        yield function

    def visit_Text(self, node):
        yield EmitText(node.value)

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
            "econtext[key] = cls(__exc, __tokens[__token][1:3])\n"
            "if handler is not None: handler(__exc)",
            cls=ErrorInfo,
            handler=load("on_error_handler"),
            key=ast.Str(s=node.name),
        )

        body += [Try(
            body=self.visit(node.node),
            handlers=[ast.ExceptHandler(
                type=ast.Tuple(elts=[Builtin("Exception")], ctx=ast.Load()),
                name=store("__exc"),
                body=(error_assignment +
                      template("del __stream[fallback:]", fallback=fallback) +
                      fallback_body
                      ),
            )]
        )]

        return body

    def visit_Content(self, node):
        name = "__content"
        body = self._engine(node.expression, store(name))

        if node.translate:
            body += emit_translate(
                name, name, load_econtext("target_language")
            )

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
                    "rcontext[KEY] = __value", KEY=ast.Str(
                        s=str(name)))

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
        body += template("s = new_list", s=stream, new_list=LIST) + \
            template("a = s.append", a=append, s=stream)

        # Visit body to generate the message body
        code = self.visit(node.node)
        body.append(Scope(code, append, stream))

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
                        value=ast.Str(s="")))

            mapping = ast.Dict(keys=keys, values=values)
        else:
            mapping = None

        # if this translation node has a name, use it as the message id
        if node.msgid:
            msgid = ast.Str(s=node.msgid)

        # emit the translation expression
        body += template(
            "if msgid: __append(translate("
            "msgid, mapping=mapping, default=default, domain=__i18n_domain, context=__i18n_context, target_language=target_language))",  # noqa:  E501 line too long
            msgid=msgid,
            default=default,
            mapping=mapping,
            target_language=load_econtext("target_language"))

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
        body.append(Scope(code, append))

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

        return set_token(stmts, node.source)

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
                        ],
                        defaults=[
                            load("__i18n_domain"),
                            load("__i18n_context")],
                    ),
                    body=body or [
                        ast.Pass()],
                ))

            key = ast.Str(s=key)

            assignment = template(
                "_slots = econtext[KEY] = DEQUE((NAME,))",
                KEY=key, NAME=fun, DEQUE=Symbol(collections.deque),
            )

            if node.extend:
                append = template("_slots.appendleft(NAME)", NAME=fun)

                assignment = [Try(
                    body=template("_slots = getname(KEY)", KEY=key),
                    handlers=[ast.ExceptHandler(body=assignment)],
                    orelse=append,
                )]

            callbacks.extend(assignment)

        assert self._macros.pop() == node.extend

        assignment = self._engine(node.expression, store("__macro"))

        return (
            callbacks +
            assignment +
            set_token(
                template("__m = __macro.include"),
                node.expression.value
            ) +
            template(
                "__m(__stream, econtext.copy(), "
                "rcontext, __i18n_domain)"
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
                elts=[ast.Str(s=name) for name in node.names],
                ctx=ast.Load())
        else:
            name = node.names[0]
            targets = [
                subscript(str(name), load(context), ast.Store())
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
            yield from template(
                "BACKUP = get(KEY, __marker)",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=str(name)),
            )

    def _leave_assignment(self, names):
        for name in names:
            yield from template(
                "if BACKUP is __marker: del econtext[KEY]\n"
                "else:                 econtext[KEY] = BACKUP",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=str(name)),
            )
