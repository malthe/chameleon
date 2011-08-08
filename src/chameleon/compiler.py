import re
import sys
import itertools
import logging
import threading
import functools

try:
    import ast
except ImportError:
    from chameleon import ast24 as ast

try:
    fast_string = str
    str = unicode
    bytes = fast_string
except NameError:
    long = int
    basestring = str
    fast_string = str

try:
    import __builtin__ as builtins
except ImportError:
    import builtins

from .astutil import load
from .astutil import store
from .astutil import param
from .astutil import swap
from .astutil import subscript
from .astutil import node_annotations
from .astutil import NameLookupRewriteVisitor
from .astutil import Comment
from .astutil import Symbol
from .astutil import Builtin

from .codegen import TemplateCodeGenerator
from .codegen import template

from .tales import StringExpr
from .i18n import fast_translate

from .nodes import Text
from .nodes import Expression
from .nodes import Assignment
from .nodes import Module
from .nodes import Context

from .config import DEBUG_MODE
from .exc import TranslationError
from .utils import DebuggingOutputStream
from .utils import Placeholder
from .utils import decode_htmlentities

log = logging.getLogger('chameleon.compiler')

COMPILER_INTERNALS_OR_DISALLOWED = set([
    "econtext",
    "rcontext",
    "translate",
    "decode",
    "convert",
    "str",
    "int",
    "float",
    "long",
    "len",
    "type",
    "None",
    "True",
    "False",
    ])


RE_MANGLE = re.compile('[\-: ]')

if DEBUG_MODE:
    LIST = template("cls()", cls=DebuggingOutputStream, mode="eval")
else:
    LIST = template("[]", mode="eval")


def identifier(prefix, suffix=None):
    return "__%s_%s" % (prefix, mangle(suffix or id(prefix)))


def mangle(string):
    return RE_MANGLE.sub('_', str(string)).replace('\n', '')


def load_econtext(name):
    return template("getitem(KEY)", KEY=ast.Str(s=name), mode="eval")


def store_econtext(name):
    name = fast_string(name)
    return subscript(name, load("econtext"), ast.Store())


def store_rcontext(name):
    name = fast_string(name)
    return subscript(name, load("rcontext"), ast.Store())


@template
def emit_node(node):  # pragma: no cover
    __append(node)


@template
def emit_node_if_non_trivial(node):  # pragma: no cover
    if node is not None:
        __append(node)


@template
def emit_convert(target, encoded=bytes, str=str, long=long):  # pragma: no cover
    if target is None:
        pass
    elif target is False:
        target = None
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
                target = convert(target)
            else:
                target = target()


@template
def emit_translate(target, msgid, default=None):  # pragma: no cover
    target = translate(msgid, default=default, domain=__i18n_domain)


@template
def emit_convert_and_escape(
    target, quote=ast.Str(s="\0"), str=str, long=long,
    encoded=bytes):  # pragma: no cover
    if target is None:
        pass
    elif target is False:
        target = None
    else:
        __tt = type(target)

        if __tt is int or __tt is float or __tt is long:
            target = str(target)
        else:
            try:
                if __tt is encoded:
                    target = decode(target)
                elif __tt is not str:
                    try:
                        target = target.__html__
                    except:
                        target = convert(target)
                    else:
                        raise RuntimeError
            except RuntimeError:
                target = target()
            else:
                if target is not None:
                    try:
                        escape = __re_needs_escape(target) is not None
                    except TypeError:
                        pass
                    else:
                        if escape:
                            # Character escape
                            if '&' in target:
                                # If there's a semicolon in the string, then
                                # it might be part of an HTML entity. We
                                # replace the ampersand character with its
                                # HTML entity counterpart only if it's
                                # precedes an HTML entity string.
                                if ';' in target:
                                    target = __re_amp.sub('&amp;', target)

                                # Otherwise, it's safe to replace all
                                # ampersands:
                                else:
                                    target = target.replace('&', '&amp;')

                            if '<' in target:
                                target = target.replace('<', '&lt;')
                            if '>' in target:
                                target = target.replace('>', '&gt;')
                            if quote in target:
                                target = target.replace(quote, '&#34;')


class ExpressionEvaluator(object):
    """Evaluates dynamic expression.

    This is not particularly efficient, but supported for legacy
    applications.

    >>> from chameleon.tales import TalesEngine
    >>> from chameleon.tales import PythonExpr

    >>> engine = TalesEngine({
    ...     'python': PythonExpr,
    ...     }, 'python')

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


class ExpressionCompiler(object):
    """Internal wrapper around a TALES-engine.

    In addition to TALES expressions (strings which may appear wrapped
    in an ``Expression`` node), this compiler also supports other
    expression node types.

    Used internally be the compiler.
    """

    initial = COMPILER_INTERNALS_OR_DISALLOWED

    global_fallback = set(builtins.__dict__)

    __slots__ = "engine", "cache", "markers", "is_builtin"

    def __init__(self, engine, cache, markers, builtin_filter):
        self.engine = engine
        self.cache = cache
        self.markers = markers
        self.is_builtin = builtin_filter

    def __call__(self, expression, target):
        if isinstance(target, basestring):
            target = store(target)

        stmts = self.translate(expression, target)

        # Apply dynamic name rewrite transform to each statement
        visitor = NameLookupRewriteVisitor(self._dynamic_transform)

        for stmt in stmts:
            visitor(stmt)

        return stmts

    def translate(self, expression, target):
        if isinstance(target, basestring):
            target = store(target)

        cached = self.cache.get(expression)

        if cached is not None:
            stmts = [ast.Assign(targets=[target], value=cached)]
        elif isinstance(expression, ast.expr):
            stmts = [ast.Assign(targets=[target], value=expression)]
            self.cache[expression] = target
        else:
            # The engine interface supports simple strings, which
            # default to expression nodes
            if isinstance(expression, basestring):
                expression = Expression(expression, True)

            kind = type(expression).__name__
            visitor = getattr(self, "visit_%s" % kind)
            stmts = visitor(expression, target)

            # Add comment
            target_id = getattr(target, "id", target)
            comment = Comment(" %r -> %s" % (expression, target_id))
            stmts.insert(0, comment)

        return stmts

    def _dynamic_transform(self, node):
        # Don't rewrite nodes that have an annotation
        annotation = node_annotations.get(node)
        if annotation is not None:
            return node

        name = node.id

        # Don't rewrite names that begin with an underscore; they are
        # internal and can be assumed to be locally defined. This
        # policy really should be part of the template program, not
        # defined here in the compiler.
        if name.startswith('__') or name in self.initial:
            return node

        # Builtins are available as static symbols
        if self.is_builtin(name):
            return ast.Name(id=name, ctx=ast.Load())

        if isinstance(node.ctx, ast.Store):
            return store_econtext(name)

        # If the name is a Python global, first try acquiring it from
        # the dynamic context, then fall back to the global.
        if name in self.global_fallback:
            return template(
                "get(key, name)",
                mode="eval",
                key=ast.Str(s=name),
                name=name
                )

        # Otherwise, simply acquire it from the dynamic context.
        return load_econtext(name)

    def visit_Expression(self, node, target):
        if node.decode:
            expression = decode_htmlentities(node.value)
        else:
            expression = node.value

        stmts = self.engine(expression, target)

        try:
            line, column = node.value.location
            filename = node.value.filename
        except AttributeError:
            line, column = 0, 0
            filename = "<string>"

        return [ast.TryExcept(
            body=stmts,
            handlers=[ast.ExceptHandler(
                body=template(
                    "rcontext.setdefault('__error__', [])."
                    "append((expression, line, col, src, sys.exc_info()[1]))\n"
                    "raise",
                    expression=ast.Str(s=expression),
                    line=ast.Num(n=line),
                    col=ast.Num(n=column),
                    src=ast.Str(s=filename),
                    sys=Symbol(sys),
                    ),
                )],
            )]

    def visit_Negate(self, node, target):
        return self.translate(node.value, target) + \
               template("TARGET = not TARGET", TARGET=target)

    def visit_Marker(self, node, target):
        self.markers.add(node.name)

        return [ast.Assign(targets=[target],
                           value=load("__marker_%s" % node.name))]

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

    def visit_Interpolation(self, node, target):
        def engine(expression, target):
            node = Expression(expression, False)
            return self.translate(node, target)

        expression = StringExpr(node.value, node.braces_required)
        return expression(target, engine)

    def visit_Translate(self, node, target):
        if node.msgid is not None:
            msgid = ast.Str(s=node.msgid)
        else:
            msgid = target
        return self.translate(node.node, target) + \
               emit_translate(target, msgid, default=target)

    def visit_Static(self, node, target):
        value = load("dummy")
        node_annotations[value] = node
        return [ast.Assign(targets=[target], value=value)]

    def visit_Builtin(self, node, target):
        value = load("dummy")
        node_annotations[value] = node
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
        'translate': Symbol(fast_translate),
        'decode': Builtin("str"),
        'convert': Builtin("str"),
        }

    lock = threading.Lock()

    def __init__(self, engine, node, builtins={}):
        self._scopes = [set()]
        self._expression_cache = {}
        self._translations = []
        self._markers = set()
        self._builtins = builtins

        is_builtin = set(builtins).__contains__

        self._engine = ExpressionCompiler(
            engine,
            self._expression_cache,
            self._markers,
            is_builtin
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
            functions += self.visit(macro)
            name = "render" if macro.name is None \
                   else "render_%s" % mangle(macro.name)
            names.append(name)

        # Prepend module-wide marker values
        for marker in self._markers:
            functions[:] = template(
                "MARKER = CLS()",
                MARKER=store("__marker_%s" % marker),
                CLS=Placeholder,
                ) + functions

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
        body += template("__i18n_domain = None")
        body += template("__re_amp = g_re_amp")
        body += template("__re_needs_escape = g_re_needs_escape")

        # Resolve defaults
        for name in self.defaults:
            body += template(
                "NAME = econtext[KEY]",
                NAME=name, KEY=ast.Str(s=name)
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
                    ],
                defaults=(),
            ),
            body=body
            )

        yield function

    def visit_Text(self, node):
        return emit_node(ast.Str(s=node.value))

    def visit_Domain(self, node):
        backup = "__previous_i18n_domain_%d" % id(node)
        return template("BACKUP = __i18n_domain", BACKUP=backup) + \
               template("__i18n_domain = NAME", NAME=ast.Str(s=node.name)) + \
               self.visit(node.node) + \
               template("__i18n_domain = BACKUP", BACKUP=backup)

    def visit_OnError(self, node):
        body = []

        fallback = identifier("__fallback")
        body += template("fallback = len(__stream)", fallback=fallback)

        body += [ast.TryExcept(
            body=self.visit(node.node),
            handlers=[ast.ExceptHandler(
                type=ast.Tuple(
                    elts=[Builtin(cls.__name__) for cls in self.exceptions],
                    ctx=ast.Load()),
                name=None,
                body=(template("del __stream[fallback:]", fallback=fallback) + \
                      self.visit(node.fallback)
                      ),
                )]
            )]

        return body

    def visit_Content(self, node):
        name = "__content"
        body = self._engine(node.expression, store(name))

        # content conversion steps
        if node.msgid is not None:
            output = emit_translate(name, name)
        elif node.escape:
            output = emit_convert_and_escape(name)
        else:
            output = emit_convert(name)

        body += output
        body += template("if NAME is not None: __append(NAME)", NAME=name)

        return body

    def visit_Interpolation(self, node):
        if node.escape:
            def convert(target):
                return emit_convert_and_escape(target, target)
        else:
            convert = emit_convert

        expression = StringExpr(node.value, node.braces_required)

        def engine(expression, target):
            node = Expression(expression, False)
            return self._engine(node, target) + \
                   convert(target)

        name = identifier("content")

        return expression(store(name), engine) + \
               emit_node_if_non_trivial(name)

    def visit_Assignment(self, node):
        for name in node.names:
            if name in COMPILER_INTERNALS_OR_DISALLOWED:
                raise TranslationError(
                    "Name disallowed by compiler: %s.", name
                    )

            if name.startswith('__'):
                raise TranslationError(
                    "Name disallowed by compiler: %s (double underscore).",
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
                    "rcontext[KEY] = __value", KEY=ast.Str(s=fast_string(name))
                    )

        return assignment

    def visit_Define(self, node):
        scope = set(self._scopes[-1])
        self._scopes.append(scope)

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
                        value=ast.Str(s=fast_string(""))))

            mapping = ast.Dict(keys=keys, values=values)
        else:
            mapping = None

        # if this translation node has a name, use it as the message id
        if node.msgid:
            msgid = ast.Str(s=node.msgid)

        # emit the translation expression
        body += template(
            "__append(translate("
            "msgid, mapping=mapping, default=default, domain=__i18n_domain))",
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

            for attribute in node.attributes:
                for stmt in self.visit(attribute):
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
        f = node.space + node.name + node.eq + node.quote + "%s" + node.quote

        if isinstance(node.expression, ast.Str):
            s = f % node.expression.s
            return template("__append(S)", S=ast.Str(s))

        target = identifier("attr", node.name)

        body = []

        body += self._engine(node.expression, store(target))

        body += emit_convert_and_escape(
            target, target, quote=ast.Str(s=node.quote)
            )

        body += template(
            "if TARGET is not None: __append(FORMAT % TARGET)",
            FORMAT=ast.Str(s=f),
            TARGET=target,
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

    def visit_UseInternalMacro(self, node):
        if node.name is None:
            render = "render"
        else:
            render = "render_%s" % mangle(node.name)

        return template("f(__stream, econtext.copy(), rcontext)", f=render) + \
               template("econtext.update(rcontext)")

    def visit_DefineSlot(self, node):
        name = "__slot_%s" % mangle(node.name)
        self._slots.add(name)
        body = self.visit(node.node)

        orelse = template("SLOT(__stream, econtext.copy(), rcontext)", SLOT=name)
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

        if self._translations is None:
            raise TranslationError(
                "Not allowed outside of translation.", node.name)

        if node.name in self._translations[-1]:
            raise TranslationError(
                "Duplicate translation name: %s." % node.name)

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

    def visit_UseExternalMacro(self, node):
        callbacks = []
        for slot in node.slots:
            key = "__slot_%s" % mangle(slot.name)
            fun = "__fill_%s" % mangle(slot.name)

            body = template("getitem = econtext.__getitem__") + \
                   template("get = econtext.get") + \
                   self.visit(slot.node)

            callbacks.append(
                ast.FunctionDef(
                    name=fun,
                    args=ast.arguments(
                        args=[
                            param("__stream"),
                            param("econtext"),
                            param("rcontext"),
                            param("__i18n_domain"),
                            ],
                        defaults=[load("__i18n_domain")],
                        ),
                    body=body or [ast.Pass()],
                ))

            key = ast.Str(s=key)

            if node.extend:
                update_body = None
            else:
                update_body = template("_slots.append(NAME)", NAME=fun)

            callbacks.append(
                ast.TryExcept(
                    body=template("_slots = getitem(KEY)", KEY=key),
                    handlers=[ast.ExceptHandler(
                        body=template(
                            "_slots = econtext[KEY] = [NAME]",
                            KEY=key, NAME=fun,
                        ))],
                    orelse=update_body
                    ))

        assignment = self._engine(node.expression, store("__macro"))

        return (
            callbacks + \
            assignment + \
            template("__macro.include(__stream, econtext.copy(), rcontext)") + \
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

        if len(node.names) > 1:
            targets = [
                ast.Tuple(elts=[
                    subscript(fast_string(name), load(context), ast.Store())
                    for name in node.names], ctx=ast.Store())
                for context in contexts
                ]

            key = ast.Tuple(
                elts=[ast.Str(s=name) for name in node.names],
                ctx=ast.Load())
        else:
            name = node.names[0]
            targets = [
                subscript(fast_string(name), load(context), ast.Store())
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
        prefix = id(self._translations[-1])
        stream = identifier("stream_%d" % prefix, name)
        append = identifier("append_%d" % prefix, name)
        return stream, append

    def _enter_assignment(self, names):
        for name in names:
            for stmt in template(
                "BACKUP = get(KEY, __marker)",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=fast_string(name)),
                ):
                yield stmt

    def _leave_assignment(self, names):
        for name in names:
            for stmt in template(
                "if BACKUP is __marker: del econtext[KEY]\n"
                "else:                 econtext[KEY] = BACKUP",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=fast_string(name)),
                ):
                yield stmt
