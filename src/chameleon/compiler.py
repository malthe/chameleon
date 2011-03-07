import re
import sys
import itertools
import logging
import threading

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

from .config import DEBUG_MODE
from .exc import TranslationError
from .utils import DebuggingOutputStream
from .utils import Placeholder
from .tokenize import Token


log = logging.getLogger('chameleon.compiler')

COMPILER_INTERNALS_OR_DISALLOWED = set([
    "stream",
    "append",
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
    return "_%s_%s" % (prefix, mangle(suffix or id(prefix)))


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
    append(node)


@template
def emit_node_if_non_trivial(node):  # pragma: no cover
    if node is not None:
        append(node)


@template
def emit_convert(target, native=bytes, str=str, long=long):  # pragma: no cover
    if target is not None:
        _tt = type(target)

        if _tt is int or _tt is float or _tt is long:
            target = native(target)
        elif _tt is native:
            target = decode(target)
        elif _tt is not str:
            try:
                target = target.__html__
            except AttributeError:
                target = convert(target)
            else:
                target = target()


@template
def emit_translate(target, msgid, default=None):  # pragma: no cover
    target = translate(msgid, default=default, domain=_i18n_domain)


@template
def emit_convert_and_escape(
    target, msgid, quote=ast.Str(s="\0"), str=str, long=long,
    native=bytes):  # pragma: no cover
    if target is None:
        pass
    elif target is False:
        target = None
    else:
        _tt = type(target)

        if _tt is int or _tt is float or _tt is long:
            target = str(target)
        else:
            try:
                if _tt is native:
                    target = decode(msgid)
                elif _tt is not str:
                    try:
                        target = target.__html__
                    except:
                        target = convert(msgid)
                    else:
                        raise RuntimeError
            except RuntimeError:
                target = target()
            else:
                if target is not None and re_needs_escape(target) is not None:
                    # Character escape
                    if '&' in target:
                        # If there's a semicolon in the string, then
                        # it might be part of an HTML entity. We
                        # replace the ampersand character with its
                        # HTML entity counterpart only if it's
                        # precedes an HTML entity string.
                        if ';' in target:
                            target = re_amp.sub('&amp;', target)

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


class ExpressionCompiler(object):
    """Internal wrapper around a TALES-engine.

    In addition to TALES expressions (strings which may appear wrapped
    in an ``Expression`` node), this compiler also supports other
    expression node types.

    Used internally be the compiler.
    """

    initial = COMPILER_INTERNALS_OR_DISALLOWED

    global_fallback = set(builtins.__dict__)

    def __init__(self, engine, cache, markers=None):
        self.engine = engine
        self.cache = cache
        self.markers = markers

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
                expression = Expression(expression)

            kind = type(expression).__name__
            visitor = getattr(self, "visit_%s" % kind)
            stmts = visitor(expression, target)

            # Add comment
            target_id = getattr(target, "id", target)
            comment = Comment(" %r -> %s" % (expression, target_id))
            stmts.insert(0, comment)

        return stmts

    @classmethod
    def _dynamic_transform(cls, node):
        # Don't rewrite nodes that have an annotation
        annotation = node_annotations.get(node)
        if annotation is not None:
            return node

        name = node.id

        # Don't rewrite names that begin with an underscore; they are
        # internal and can be assumed to be locally defined. This
        # policy really should be part of the template program, not
        # defined here in the compiler.
        if name.startswith('_') or name in cls.initial:
            return node

        if isinstance(node.ctx, ast.Store):
            return store_econtext(name)

        # If the name is a Python global, first try acquiring it from
        # the dynamic context, then fall back to the global.
        if name in cls.global_fallback:
            return template(
                "get(key, name)",
                mode="eval",
                key=ast.Str(s=name),
                name=name
                )

        # Otherwise, simply acquire it from the dynamic context.
        return load_econtext(name)

    def visit_Expression(self, node, target):
        stmts = self.engine(node.value, target)

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
                    expression=ast.Str(s=node.value),
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
                           value=load("_marker_%s" % node.name))]

    def visit_Identity(self, node, target):
        expression = self.translate(node.expression, "_expression")
        value = self.translate(node.value, "_value")

        return expression + value + \
               template("TARGET = _expression is _value", TARGET=target)

    def visit_Equality(self, node, target):
        expression = self.translate(node.expression, "_expression")
        value = self.translate(node.value, "_value")

        return expression + value + \
               template("TARGET = _expression == _value", TARGET=target)

    def visit_Interpolation(self, node, target):
        def engine(expression, target):
            node = Expression(expression)
            return self.translate(node, target)

        expression = StringExpr(node.value)
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

    def __init__(self, engine, node):
        self._scopes = [set()]
        self._expression_cache = {}
        self._translations = []
        self._markers = set()

        self._engine = ExpressionCompiler(
            engine,
            self._expression_cache,
            self._markers
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

    def visit_Program(self, node):
        return self.visit_MacroProgram(node)

    def visit_MacroProgram(self, node):
        body = []

        body += template("import re")
        body += template("import functools")
        body += template("_marker = object()")
        body += template(
            r"g_re_amp = re.compile(r'&(?!([A-Za-z]+|#[0-9]+);)')"
        )
        body += template(
            r"g_re_needs_escape = re.compile(r'[&<>\"\']').search")

        body += template(
            r"re_whitespace = "
            r"functools.partial(re.compile('\s+').sub, ' ')",
        )

        # Visit defined macros
        for macro in getattr(node, "macros", ()):
            body += self.visit(macro)

        # Visit (implicit) main macro
        body += self.visit_Macro(node)

        # Prepend module-wide marker values
        for marker in self._markers:
            body[:] = template(
                "MARKER = CLS()",
                MARKER=store("_marker_%s" % marker),
                CLS=Placeholder,
                ) + body

        return body

    def visit_Macro(self, node):
        body = []

        # Initialization
        body += template("append = stream.append")
        body += template("getitem = econtext.__getitem__")
        body += template("get = econtext.get")
        body += template("_i18n_domain = None")
        body += template("re_amp = g_re_amp")
        body += template("re_needs_escape = g_re_needs_escape")

        # Resolve defaults
        for name in self.defaults:
            body += template(
                "NAME = getitem(KEY)",
                NAME=name, KEY=ast.Str(s=name)
            )

        # Visit macro body
        body += itertools.chain(*tuple(map(self.visit, node.body)))

        function_name = "render" if node.name is None else \
                        "render_%s" % mangle(node.name)

        function = ast.FunctionDef(
            name=function_name, args=ast.arguments(
                args=[
                    param("stream"),
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
        backup = "_previous_i18n_domain_%d" % id(node)
        return template("BACKUP = _i18n_domain", BACKUP=backup) + \
               template("_i18n_domain = NAME", NAME=ast.Str(s=node.name)) + \
               self.visit(node.node) + \
               template("_i18n_domain = BACKUP", BACKUP=backup)

    def visit_OnError(self, node):
        body = []

        fallback = identifier("_fallback")
        body += template("fallback = len(stream)", fallback=fallback)

        body += [ast.TryExcept(
            body=self.visit(node.node),
            handlers=[ast.ExceptHandler(
                type=ast.Tuple(
                    elts=[Builtin(cls.__name__) for cls in self.exceptions],
                    ctx=ast.Load()),
                name=None,
                body=(template("del stream[fallback:]", fallback=fallback) + \
                      self.visit(node.fallback)
                      ),
                )]
            )]

        return body

    def visit_Content(self, node):
        name = "_content"
        body = self._engine(node.expression, store(name))

        # content conversion steps
        if node.msgid is not None:
            output = emit_translate(name, name)
        elif node.escape:
            output = emit_convert_and_escape(name, name)
        else:
            output = emit_convert(name)

        body += output
        body += template("if NAME is not None: append(NAME)", NAME=name)

        return body

    def visit_Interpolation(self, node):
        if node.escape:
            def convert(target):
                return emit_convert_and_escape(target, target)
        else:
            convert = emit_convert

        def engine(expression, target):
            node = Expression(expression)
            return self._engine(node, target) + \
                   convert(target)

        expression = StringExpr(node.value)

        name = identifier("content")

        return expression(store(name), engine) + \
               emit_node_if_non_trivial(load(name))

    def visit_Assignment(self, node):
        for name in node.names:
            if name in COMPILER_INTERNALS_OR_DISALLOWED:
                raise TranslationError(
                    "Name disallowed by compiler: %s." % name
                    )

        assignment = self._engine(node.expression, store("_value"))

        if len(node.names) != 1:
            target = ast.Tuple(
                elts=[store_econtext(name) for name in node.names],
                ctx=ast.Store(),
            )
        else:
            target = store_econtext(node.names[0])

        assignment.append(ast.Assign(targets=[target], value=load("_value")))

        for name in node.names:
            if not node.local:
                assignment += template(
                    "rcontext[KEY] = _value", KEY=ast.Str(s=fast_string(name))
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
        target = "_condition"
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
        swap(ast.Suite(body=code), load(append), "append")
        body += code

        # Reduce white space and assign as message id
        msgid = identifier("msgid", id(node))
        body += template(
            "msgid = re_whitespace(''.join(stream)).strip()",
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
            "append(translate("
            "msgid, mapping=mapping, default=default, domain=_i18n_domain))",
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
        body = []

        target = identifier("attr", node.name)
        body += self._engine(node.expression, store(target))

        if node.escape:
            body += emit_convert_and_escape(
                target, target, quote=ast.Str(s=node.quote)
                )

        f = node.space + node.name + node.eq + node.quote + "%s" + node.quote
        body += template(
            "if TARGET is not None: append(FORMAT % TARGET)",
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

        return template("f(stream, econtext.copy(), rcontext)", f=render) + \
               template("econtext.update(rcontext)")

    def visit_DefineSlot(self, node):
        name = "_slot_%s" % mangle(node.name)
        body = self.visit(node.node)

        return [
            ast.TryExcept(
                body=template("_slot = getitem(KEY).pop()",
                              KEY=ast.Str(s=name)),
                handlers=[ast.ExceptHandler(
                    body=body or [ast.Pass()],
                    )],
                orelse=template("_slot(stream, econtext.copy(), econtext)"),
                )
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
        swap(ast.Suite(body=code), load(append), "append")
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
            name = "_slot_%s" % mangle(slot.name)

            body = template("getitem = econtext.__getitem__") + \
                   template("get = econtext.get") + \
                   self.visit(slot.node)

            callbacks.append(
                ast.FunctionDef(
                    name=name,
                    args=ast.arguments(
                        args=[
                            param("stream"),
                            param("econtext"),
                            param("rcontext"),
                            param("_i18n_domain"),
                            ],
                        defaults=[load("_i18n_domain")],
                        ),
                    body=body or [ast.Pass()],
                ))

            key = ast.Str(s=name)

            if node.extend:
                update_body = None
            else:
                update_body = template("_slots.append(NAME)", NAME=name)

            callbacks.append(
                ast.TryExcept(
                    body=template("_slots = getitem(KEY)", KEY=key),
                    handlers=[ast.ExceptHandler(
                        body=template(
                            "_slots = econtext[KEY] = [NAME]",
                            KEY=key, NAME=name
                        ))],
                    orelse=update_body
                    ))

        assignment = self._engine(node.expression, store("_macro"))

        return (
            callbacks + \
            assignment + \
            template("_macro.include(stream, econtext.copy(), rcontext)") + \
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

        index = identifier("_index", id(node))
        assignment = [ast.Assign(targets=targets, value=load("_item"))]

        # Make repeat assignment in outer loop
        names = node.names
        local = node.local

        outer = self._engine(node.expression, store("_iterator"))

        if local:
            outer[:] = list(self._enter_assignment(names)) + outer

        outer += template(
            "_iterator, INDEX = getitem('repeat')(key, _iterator)",
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
            "if INDEX > 0: append(WHITESPACE)",
            INDEX=index, WHITESPACE=ast.Str(s=node.whitespace)
            )

        # Main repeat loop
        outer += [ast.For(
            target=store("_item"),
            iter=load("_iterator"),
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
                "BACKUP = get(KEY, _marker)",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=fast_string(name)),
                ):
                yield stmt

    def _leave_assignment(self, names):
        for name in names:
            for stmt in template(
                "if BACKUP is _marker: del econtext[KEY]\n"
                "else:                 econtext[KEY] = BACKUP",
                BACKUP=identifier("backup_%s" % name, id(names)),
                KEY=ast.Str(s=fast_string(name)),
                ):
                yield stmt
