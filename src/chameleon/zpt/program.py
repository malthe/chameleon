import re

try:
    import ast
except ImportError:
    from chameleon import ast25 as ast

try:
    str = unicode
except NameError:
    long = int

from functools import partial
from copy import copy

from ..program import ElementProgram

from ..namespaces import XML_NS
from ..namespaces import XMLNS_NS
from ..namespaces import I18N_NS as I18N
from ..namespaces import TAL_NS as TAL
from ..namespaces import METAL_NS as METAL
from ..namespaces import META_NS as META

from ..astutil import Static
from ..astutil import parse
from ..astutil import marker

from .. import tal
from .. import metal
from .. import i18n
from .. import nodes

from ..exc import LanguageError
from ..exc import ParseError
from ..exc import CompilationError

from ..utils import decode_htmlentities

try:
    str = unicode
except NameError:
    long = int


missing = object()

re_trim = re.compile(r'($\s+|\s+^)', re.MULTILINE)

EMPTY_DICT = Static(ast.Dict(keys=[], values=[]))


def skip(node):
    return node


def wrap(node, *wrappers):
    for wrapper in reversed(wrappers):
        node = wrapper(node)
    return node


def validate_attributes(attributes, namespace, whitelist):
    for ns, name in attributes:
        if ns == namespace and name not in whitelist:
            raise CompilationError(
                "Bad attribute for namespace '%s'" % ns, name
                )


class MacroProgram(ElementProgram):
    """Visitor class that generates a program for the ZPT language."""

    DEFAULT_NAMESPACES = {
        'xmlns': XMLNS_NS,
        'xml': XML_NS,
        'tal': TAL,
        'metal': METAL,
        'i18n': I18N,
        'meta': META,
        }

    DROP_NS = TAL, METAL, I18N, META

    VARIABLE_BLACKLIST = "default", "repeat", "nothing", \
                         "convert", "decode", "translate"

    _interpolation_enabled = True
    _whitespace = "\n"
    _last = ""

    # Macro name (always trivial for a macro program)
    name = None

    # This default marker value has the semantics that if an
    # expression evaluates to that value, the expression default value
    # is returned. For an attribute, if there is no default, this
    # means that the attribute is dropped.
    default_marker = None

    # Escape mode (true value means XML-escape)
    escape = True

    # Attributes which should have boolean behavior (on true, the
    # value takes the attribute name, on false, the attribute is
    # dropped)
    boolean_attributes = set()

    # If provided, this should be a set of attributes for implicit
    # translation. Any attribute whose name is included in the set
    # will be translated even without explicit markup. Note that all
    # values should be lowercase strings.
    implicit_i18n_attributes = set()

    # If set, text will be translated even without explicit markup.
    implicit_i18n_translate = False

    # If set, additional attribute whitespace will be stripped.
    trim_attribute_space = False

    def __init__(self, *args, **kwargs):
        # Internal array for switch statements
        self._switches = []

        # Internal array for current use macro level
        self._use_macro = []

        # Internal array for current interpolation status
        self._interpolation = [True]

        # Internal dictionary of macro definitions
        self._macros = {}

        # Apply default values from **kwargs to self
        self._pop_defaults(
            kwargs,
            'boolean_attributes',
            'default_marker',
            'escape',
            'implicit_i18n_translate',
            'implicit_i18n_attributes',
            'trim_attribute_space',
            )

        super(MacroProgram, self).__init__(*args, **kwargs)

    @property
    def macros(self):
        macros = list(self._macros.items())
        macros.append((None, nodes.Sequence(self.body)))

        return tuple(
            nodes.Macro(name, [nodes.Context(node)])
            for name, node in macros
            )

    def visit_default(self, node):
        return nodes.Text(node)

    def visit_element(self, start, end, children):
        ns = start['ns_attrs']

        for (prefix, attr), encoded in tuple(ns.items()):
            if prefix == TAL:
                ns[prefix, attr] = decode_htmlentities(encoded)

        # Validate namespace attributes
        validate_attributes(ns, TAL, tal.WHITELIST)
        validate_attributes(ns, METAL, metal.WHITELIST)
        validate_attributes(ns, I18N, i18n.WHITELIST)

        # Check attributes for language errors
        self._check_attributes(start['namespace'], ns)

        # Remember whitespace for item repetition
        if self._last is not None:
            self._whitespace = "\n" + " " * len(self._last.rsplit('\n', 1)[-1])

        # Set element-local whitespace
        whitespace = self._whitespace

        # Set up switch
        try:
            clause = ns[TAL, 'switch']
        except KeyError:
            switch = None
        else:
            value = nodes.Value(clause)
            switch = value, nodes.Copy(value)

        self._switches.append(switch)

        body = []

        # Include macro
        use_macro = ns.get((METAL, 'use-macro'))
        extend_macro = ns.get((METAL, 'extend-macro'))
        if use_macro or extend_macro:
            omit = True
            slots = []
            self._use_macro.append(slots)

            if use_macro:
                inner = nodes.UseExternalMacro(
                    nodes.Value(use_macro), slots, False
                    )
            else:
                inner = nodes.UseExternalMacro(
                    nodes.Value(extend_macro), slots, True
                    )
        # -or- include tag
        else:
            content = nodes.Sequence(body)

            # tal:content
            try:
                clause = ns[TAL, 'content']
            except KeyError:
                pass
            else:
                key, value = tal.parse_substitution(clause)
                xlate = True if ns.get((I18N, 'translate')) == '' else False
                content = self._make_content_node(value, content, key, xlate)

                if end is None:
                    # Make sure start-tag has opening suffix.
                    start['suffix']  = ">"

                    # Explicitly set end-tag.
                    end = {
                        'prefix': '</',
                        'name': start['name'],
                        'space': '',
                        'suffix': '>'
                        }

            # i18n:translate
            try:
                clause = ns[I18N, 'translate']
            except KeyError:
                pass
            else:
                dynamic = ns.get((TAL, 'content')) or ns.get((TAL, 'replace'))

                if not dynamic:
                    content = nodes.Translate(clause, content)

            # tal:attributes
            try:
                clause = ns[TAL, 'attributes']
            except KeyError:
                TAL_ATTRIBUTES = []
            else:
                TAL_ATTRIBUTES = tal.parse_attributes(clause)

            # i18n:attributes
            try:
                clause = ns[I18N, 'attributes']
            except KeyError:
                I18N_ATTRIBUTES = {}
            else:
                I18N_ATTRIBUTES = i18n.parse_attributes(clause)

            # Prepare attributes from TAL language
            prepared = tal.prepare_attributes(
                start['attrs'], TAL_ATTRIBUTES,
                I18N_ATTRIBUTES, ns, self.DROP_NS
                )

            # Create attribute nodes
            STATIC_ATTRIBUTES = self._create_static_attributes(prepared)
            ATTRIBUTES = self._create_attributes_nodes(
                prepared, I18N_ATTRIBUTES, STATIC_ATTRIBUTES
                )

            # Start- and end nodes
            start_tag = nodes.Start(
                start['name'],
                self._maybe_trim(start['prefix']),
                self._maybe_trim(start['suffix']),
                ATTRIBUTES
                )

            end_tag = nodes.End(
                end['name'],
                end['space'],
                self._maybe_trim(end['prefix']),
                self._maybe_trim(end['suffix']),
                ) if end is not None else None

            # tal:omit-tag
            try:
                clause = ns[TAL, 'omit-tag']
            except KeyError:
                omit = False
            else:
                clause = clause.strip()

                if clause == "":
                    omit = True
                else:
                    expression = nodes.Negate(nodes.Value(clause))
                    omit = expression

                    # Wrap start- and end-tags in condition
                    start_tag = nodes.Condition(expression, start_tag)

                    if end_tag is not None:
                        end_tag = nodes.Condition(expression, end_tag)

            if omit is True or start['namespace'] in self.DROP_NS:
                inner = content
            else:
                inner = nodes.Element(
                    start_tag,
                    end_tag,
                    content,
                    )

                # Assign static attributes dictionary to "attrs" value
                inner = nodes.Define(
                    [nodes.Alias(["attrs"], STATIC_ATTRIBUTES or EMPTY_DICT)],
                    inner,
                    )

                if omit is not False:
                    inner = nodes.Cache([omit], inner)

            # tal:replace
            try:
                clause = ns[TAL, 'replace']
            except KeyError:
                pass
            else:
                key, value = tal.parse_substitution(clause)
                xlate = True if ns.get((I18N, 'translate')) == '' else False
                inner = self._make_content_node(value, inner, key, xlate)

        # metal:define-slot
        try:
            clause = ns[METAL, 'define-slot']
        except KeyError:
            DEFINE_SLOT = skip
        else:
            DEFINE_SLOT = partial(nodes.DefineSlot, clause)

        # tal:define
        try:
            clause = ns[TAL, 'define']
        except KeyError:
            DEFINE = skip
        else:
            defines = tal.parse_defines(clause)
            if defines is None:
                raise ParseError("Invalid define syntax.", clause)

            DEFINE = partial(
                nodes.Define,
                [nodes.Assignment(
                    names, nodes.Value(expr), context == "local")
                 for (context, names, expr) in defines],
                )

        # tal:case
        try:
            clause = ns[TAL, 'case']
        except KeyError:
            CASE = skip
        else:
            value = nodes.Value(clause)
            for switch in reversed(self._switches):
                if switch is not None:
                    break
            else:
                raise LanguageError(
                    "Must define switch on a parent element.", clause
                    )

            CASE = lambda node: nodes.Define(
                [nodes.Alias(["default"], switch[1], False)],
                nodes.Condition(
                    nodes.Equality(switch[0], value),
                    nodes.Cancel([switch[0]], node),
                ))

        # tal:repeat
        try:
            clause = ns[TAL, 'repeat']
        except KeyError:
            REPEAT = skip
        else:
            defines = tal.parse_defines(clause)
            assert len(defines) == 1
            context, names, expr = defines[0]

            expression = nodes.Value(expr)

            if start['namespace'] == TAL:
                self._last = None
                self._whitespace = whitespace.lstrip('\n')
                whitespace = ""

            REPEAT = partial(
                nodes.Repeat,
                names,
                expression,
                context == "local",
                whitespace
                )

        # tal:condition
        try:
            clause = ns[TAL, 'condition']
        except KeyError:
            CONDITION = skip
        else:
            expression = nodes.Value(clause)
            CONDITION = partial(nodes.Condition, expression)

        # tal:switch
        if switch is None:
            SWITCH = skip
        else:
            SWITCH = partial(nodes.Cache, list(switch))

        # i18n:domain
        try:
            clause = ns[I18N, 'domain']
        except KeyError:
            DOMAIN = skip
        else:
            DOMAIN = partial(nodes.Domain, clause)

        # i18n:context
        try:
            clause = ns[I18N, 'context']
        except KeyError:
            CONTEXT = skip
        else:
            CONTEXT = partial(nodes.TxContext, clause)

        # i18n:name
        try:
            clause = ns[I18N, 'name']
        except KeyError:
            NAME = skip
        else:
            if not clause.strip():
                NAME = skip
            else:
                NAME = partial(nodes.Name, clause)

        # The "slot" node next is the first node level that can serve
        # as a macro slot
        slot = wrap(
            inner,
            DEFINE_SLOT,
            DEFINE,
            CASE,
            CONDITION,
            REPEAT,
            SWITCH,
            DOMAIN,
            CONTEXT,
            )

        # metal:fill-slot
        try:
            clause = ns[METAL, 'fill-slot']
        except KeyError:
            pass
        else:
            if not clause.strip():
                raise LanguageError(
                    "Must provide a non-trivial string for metal:fill-slot.",
                    clause
                )

            index = -(1 + int(bool(use_macro or extend_macro)))

            try:
                slots = self._use_macro[index]
            except IndexError:
                raise LanguageError(
                    "Cannot use metal:fill-slot without metal:use-macro.",
                    clause
                    )

            slots = self._use_macro[index]
            slots.append(nodes.FillSlot(clause, slot))

        # metal:define-macro
        try:
            clause = ns[METAL, 'define-macro']
        except KeyError:
            pass
        else:
            self._macros[clause] = slot
            slot = nodes.UseInternalMacro(clause)

        slot = wrap(
            slot,
            NAME
            )

        # tal:on-error
        try:
            clause = ns[TAL, 'on-error']
        except KeyError:
            ON_ERROR = skip
        else:
            key, value = tal.parse_substitution(clause)
            translate = True if ns.get((I18N, 'translate')) == '' else False

            fallback = self._make_content_node(value, None, key, translate)

            if omit is False and start['namespace'] not in self.DROP_NS:
                start_tag = copy(start_tag)

                start_tag.attributes = nodes.Sequence(
                    start_tag.attributes.extract(
                        lambda attribute:
                        isinstance(attribute, nodes.Attribute) and
                        isinstance(attribute.expression, ast.Str)
                    )
                )

                if end_tag is None:
                    # Make sure start-tag has opening suffix. We don't
                    # allow self-closing element here.
                    start_tag.suffix  = ">"

                    # Explicitly set end-tag.
                    end_tag = nodes.End(start_tag.name, '', '</', '>',)

                fallback = nodes.Element(
                    start_tag,
                    end_tag,
                    fallback,
                )

            ON_ERROR = partial(nodes.OnError, fallback, 'error')

        clause = ns.get((META, 'interpolation'))
        if clause in ('false', 'off'):
            INTERPOLATION = False
        elif clause in ('true', 'on'):
            INTERPOLATION = True
        elif clause is None:
            INTERPOLATION = self._interpolation[-1]
        else:
            raise LanguageError("Bad interpolation setting.", clause)

        self._interpolation.append(INTERPOLATION)

        # Visit content body
        for child in children:
            body.append(self.visit(*child))

        self._switches.pop()
        self._interpolation.pop()

        if use_macro:
            self._use_macro.pop()

        return wrap(
            slot,
            ON_ERROR
            )

    def visit_start_tag(self, start):
        return self.visit_element(start, None, [])

    def visit_cdata(self, node):
        if not self._interpolation[-1] or not '${' in node:
            return nodes.Text(node)

        expr = nodes.Substitution(node, ())
        return nodes.Interpolation(expr, True, False)

    def visit_comment(self, node):
        if node.startswith('<!--!'):
            return

        if node.startswith('<!--?'):
            return nodes.Text('<!--' + node.lstrip('<!-?'))

        if not self._interpolation[-1] or not '${' in node:
            return nodes.Text(node)

        char_escape = ('&', '<', '>') if self.escape else ()
        expression = nodes.Substitution(node[4:-3], char_escape)

        return nodes.Sequence(
            [nodes.Text(node[:4]),
             nodes.Interpolation(expression, True, False),
             nodes.Text(node[-3:])
             ])

    def visit_processing_instruction(self, node):
        if node['name'] != 'python':
            text = '<?' + node['name'] + node['text'] + '?>'
            return self.visit_text(text)

        return nodes.CodeBlock(node['text'])

    def visit_text(self, node):
        self._last = node

        translation = self.implicit_i18n_translate

        if self._interpolation[-1] and '${' in node:
            char_escape = ('&', '<', '>') if self.escape else ()
            expression = nodes.Substitution(node, char_escape)
            return nodes.Interpolation(expression, True, translation)

        if not translation:
            return nodes.Text(node)

        match = re.search(r'(\s*)(.*\S)(\s*)', node, flags=re.DOTALL)
        if match is not None:
            prefix, text, suffix = match.groups()
            normalized = re.sub('\s+', ' ', text)
            return nodes.Sequence([
                nodes.Text(prefix),
                nodes.Translate(normalized, nodes.Text(normalized)),
                nodes.Text(suffix),
            ])
        else:
            return nodes.Text(node)

    def _pop_defaults(self, kwargs, *attributes):
        for attribute in attributes:
            default = getattr(self, attribute)
            value = kwargs.pop(attribute, default)
            setattr(self, attribute, value)

    def _check_attributes(self, namespace, ns):
        if namespace in self.DROP_NS and ns.get((TAL, 'attributes')):
            raise LanguageError(
                "Dynamic attributes not allowed on elements of "
                "the namespace: %s." % namespace,
                ns[TAL, 'attributes'],
                )

        script = ns.get((TAL, 'script'))
        if script is not None:
            raise LanguageError(
                "The script attribute is unsupported.", script)

        tal_content = ns.get((TAL, 'content'))
        if tal_content and ns.get((TAL, 'replace')):
            raise LanguageError(
                "You cannot use tal:content and tal:replace at the same time.",
                tal_content
                )

        if tal_content and ns.get((I18N, 'translate')):
            raise LanguageError(
                "You cannot use tal:content with non-trivial i18n:translate.",
                tal_content
                )

    def _make_content_node(self, expression, default, key, translate):
        value = nodes.Value(expression)
        char_escape = ('&', '<', '>') if key == 'text' else ()
        content = nodes.Content(value, char_escape, translate)

        if default is not None:
            content = nodes.Condition(
                nodes.Identity(value, marker("default")),
                default,
                content,
                )

            # Cache expression to avoid duplicate evaluation
            content = nodes.Cache([value], content)

            # Define local marker "default"
            content = nodes.Define(
                [nodes.Alias(["default"], marker("default"))],
                content
                )

        return content

    def _create_attributes_nodes(self, prepared, I18N_ATTRIBUTES, STATIC):
        attributes = []

        names = [attr[0] for attr in prepared]
        filtering = [[]]

        for i, (name, text, quote, space, eq, expr) in enumerate(prepared):
            implicit_i18n = (
                name is not None and
                name.lower() in self.implicit_i18n_attributes
            )

            char_escape = ('&', '<', '>', quote)

            # Use a provided default text as the default marker
            # (aliased to the name ``default``), otherwise use the
            # program's default marker value.
            if text is not None:
                default_marker = ast.Str(s=text)
            else:
                default_marker = self.default_marker

            msgid = I18N_ATTRIBUTES.get(name, missing)

            # If (by heuristic) ``text`` contains one or more
            # interpolation expressions, apply interpolation
            # substitution to the text
            if expr is None and text is not None and '${' in text:
                expr = nodes.Substitution(text, char_escape, None)
                translation = implicit_i18n and msgid is missing
                value = nodes.Interpolation(expr, True, translation)
                default_marker = self.default_marker

            # If the expression is non-trivial, the attribute is
            # dynamic (computed).
            elif expr is not None:
                if name is None:
                    expression = nodes.Value(expr)
                    value = nodes.DictAttributes(
                        expression, ('&', '<', '>', '"'), '"',
                        set(filter(None, names[i:]))
                    )
                    for fs in filtering:
                        fs.append(expression)
                    filtering.append([])
                elif name in self.boolean_attributes:
                    value = nodes.Boolean(expr, name)
                else:
                    if text is not None:
                        default = default_marker
                    else:
                        default = None

                    value = nodes.Substitution(expr, char_escape, default)

            # Otherwise, it's a static attribute. We don't include it
            # here if there's one or more "computed" attributes
            # (dynamic, from one or more dict values).
            else:
                value = ast.Str(s=text)
                if msgid is missing and implicit_i18n:
                    msgid = text

            if name is not None:
                # If translation is required, wrap in a translation
                # clause
                if msgid is not missing:
                    value = nodes.Translate(msgid, value)

                space = self._maybe_trim(space)
                fs = filtering[-1]
                attribute = nodes.Attribute(name, value, quote, eq, space, fs)

                if not isinstance(value, ast.Str):
                    # Always define a ``default`` alias for non-static
                    # expressions.
                    attribute = nodes.Define(
                        [nodes.Alias(["default"], default_marker)],
                        attribute,
                        )

                value = attribute

            attributes.append(value)

        result = nodes.Sequence(attributes)

        fs = filtering[0]
        if fs:
            return nodes.Cache(fs, result)

        return result

    def _create_static_attributes(self, prepared):
        static_attrs = {}

        for name, text, quote, space, eq, expr in prepared:
            if name is None:
                continue

            static_attrs[name] = text if text is not None else expr

        if not static_attrs:
            return

        return Static(parse(repr(static_attrs)).body)

    def _maybe_trim(self, string):
        if self.trim_attribute_space:
            return re_trim.sub(" ", string)

        return string
