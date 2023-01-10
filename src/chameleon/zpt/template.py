from functools import partial
from hashlib import sha256
from os.path import dirname

from ..astutil import Symbol
from ..compiler import ExpressionEngine
from ..i18n import simple_translate
from ..loader import TemplateLoader
from ..tal import RepeatDict
from ..tales import DEFAULT_MARKER
from ..tales import ExistsExpr
from ..tales import ExpressionParser
from ..tales import ImportExpr
from ..tales import NotExpr
from ..tales import ProxyExpr
from ..tales import PythonExpr
from ..tales import StringExpr
from ..tales import StructureExpr
from ..template import BaseTemplate
from ..template import BaseTemplateFile
from .program import MacroProgram


try:
    bytes
except NameError:
    bytes = str


class PageTemplate(BaseTemplate):
    """Constructor for the page template language.

    Takes a string input as the only positional argument::

      template = PageTemplate("<div>Hello, ${name}.</div>")

    Configuration (keyword arguments):

      ``auto_reload``

        Enables automatic reload of templates. This is mostly useful
        in a development mode since it takes a significant performance
        hit.

      ``default_expression``

        Set the default expression type. The default setting is
        ``python``.

      ``encoding``

        The default text substitution value is a string.

        Pass an encoding to allow encoded byte string input
        (e.g. UTF-8).

      ``boolean_attributes``

        Attributes included in this set are treated as booleans: if a
        true value is provided, the attribute value is the attribute
        name, e.g.::

            boolean_attributes = {"selected"}

        If we insert an attribute with the name "selected" and
        provide a true value, the attribute will be rendered::

            selected="selected"

        If a false attribute is provided (including the empty string),
        the attribute is dropped.

        The special return value ``default`` drops or inserts the
        attribute based on the value element attribute value.

      ``translate``

        Use this option to set a translation function.

        Example::

          def translate(msgid, domain=None, mapping=None, default=None,
                        context=None):
              ...
              return translation

        Note that if ``target_language`` is provided at render time,
        the translation function must support this argument.

      ``implicit_i18n_translate``

        Enables implicit translation for text appearing inside
        elements. Default setting is ``False``.

        While implicit translation does work for text that includes
        expression interpolation, each expression must be simply a
        variable name (e.g. ``${foo}``); otherwise, the text will not
        be marked for translation.

      ``implicit_i18n_attributes``

        Any attribute contained in this set will be marked for
        implicit translation. Each entry must be a lowercase string.

        Example::

          implicit_i18n_attributes = set(['alt', 'title'])

      ``on_error_handler``

        This is an optional exception handler that is invoked during the
        "on-error" fallback block.

      ``strict``

        Enabled by default. If disabled, expressions are only required
        to be valid at evaluation time.

        This setting exists to provide compatibility with the
        reference implementation which compiles expressions at
        evaluation time.

      ``trim_attribute_space``

        If set, additional attribute whitespace will be stripped.

      ``restricted_namespace``

        True by default. If set False, ignored all namespace except chameleon
        default namespaces. It will be useful working with attributes based
        javascript template renderer like VueJS.

        Example:

          <div v-bind:id="dynamicId"></div>
          <button v-on:click="greet">Greet</button>
          <button @click="greet">Greet</button>

      ``tokenizer``

        None by default. If provided, this tokenizer is used instead of the
        default (which is selected based on the template mode parameter.)

      ``value_repr``

        This can be used to override the default value representation
        function which is used to format values when formatting an
        exception output. The function must not raise an exception (it
        should be safe to call with any value).

      ``default_marker``

        This default marker is used as the marker object bound to the `default`
        name available to any expression. The semantics is such that if an
        expression evaluates to the marker object, the default action is used;
        for an attribute expression, this is the static attribute text; for an
        element this is the static element text. If there is no static text
        then the default action is similar to an expression result of `None`.

    Output is of type ``str``.

    """

    expression_types = {
        'python': PythonExpr,
        'string': StringExpr,
        'not': NotExpr,
        'exists': ExistsExpr,
        'import': ImportExpr,
        'structure': StructureExpr,
    }

    default_expression = 'python'

    translate = staticmethod(simple_translate)

    encoding = None

    boolean_attributes = set()

    mode = "xml"

    implicit_i18n_translate = False

    implicit_i18n_attributes = set()

    trim_attribute_space = False

    enable_data_attributes = False

    enable_comment_interpolation = True

    on_error_handler = None

    restricted_namespace = True

    tokenizer = None

    default_marker = Symbol(DEFAULT_MARKER)

    def __init__(self, body, **config):
        self.macros = Macros(self)
        super().__init__(body, **config)

    def __getitem__(self, name):
        return self.macros[name]

    @property
    def builtins(self):
        return self._builtins()

    @property
    def engine(self):
        return partial(
            ExpressionEngine,
            self.expression_parser,
            default_marker=self.default_marker,
        )

    @property
    def expression_parser(self):
        return ExpressionParser(self.expression_types, self.default_expression)

    def parse(self, body):
        return MacroProgram(
            body, self.mode, self.filename,
            escape=True if self.mode == "xml" else False,
            default_marker=self.default_marker,
            boolean_attributes=self.boolean_attributes,
            implicit_i18n_translate=self.implicit_i18n_translate,
            implicit_i18n_attributes=self.implicit_i18n_attributes,
            trim_attribute_space=self.trim_attribute_space,
            enable_data_attributes=self.enable_data_attributes,
            enable_comment_interpolation=self.enable_comment_interpolation,
            restricted_namespace=self.restricted_namespace,
            tokenizer=self.tokenizer
        )

    def render(self, encoding=None, **_kw):
        """Render template to string.

        If providd, the ``encoding`` argument overrides the template
        default value.

        Additional keyword arguments are passed as template variables.

        In addition, some also have a special meaning:

          ``translate``

            This keyword argument will override the default template
            translate function.

          ``target_language``

            This will be used as the default argument to the translate
            function if no `i18n:target` value is provided.

            If not provided, the `translate` function will need to
            negotiate a language based on the provided context.
        """

        translate = _kw.get('translate')
        if translate is None:
            translate = self.translate

            # This should not be necessary, but we include it for
            # backward compatibility.
            if translate is None:
                translate = type(self).translate

        encoding = encoding if encoding is not None else self.encoding
        if encoding is not None:
            def translate(msgid, txl=translate, encoding=encoding, **kwargs):
                if isinstance(msgid, bytes):
                    msgid = bytes.decode(msgid, encoding)
                return txl(msgid, **kwargs)

            def decode(inst, encoding=encoding):
                return bytes.decode(inst, encoding, 'ignore')
        else:
            decode = bytes.decode

        target_language = _kw.get('target_language')

        setdefault = _kw.setdefault
        setdefault("__translate", translate)
        setdefault("__convert",
                   partial(translate, target_language=target_language))
        setdefault("__decode", decode)
        setdefault("target_language", None)
        setdefault("__on_error_handler", self.on_error_handler)

        # Make sure we have a repeat dictionary
        if 'repeat' not in _kw:
            _kw['repeat'] = RepeatDict({})

        return super().render(**_kw)

    def include(self, *args, **kwargs):
        self.cook_check()
        self._render(*args, **kwargs)

    def digest(self, body, names):
        hex = super().digest(body, names)
        if isinstance(hex, str):
            hex = hex.encode('utf-8')
        digest = sha256(hex)
        digest.update(';'.join(names).encode('utf-8'))

        for attr in (
            'trim_attribute_space',
            'implicit_i18n_translate',
            'strict'
        ):
            v = getattr(self, attr)
            digest.update(
                (";{}={}".format(attr, str(v))).encode('ascii')
            )

            return digest.hexdigest()[:32]

    def _builtins(self):
        return {
            'template': self,
            'macros': self.macros,
            'nothing': None,
        }


class PageTemplateFile(PageTemplate, BaseTemplateFile):
    """File-based constructor.

    Takes a string input as the only positional argument::

      template = PageTemplateFile(absolute_path)

    Note that the file-based template class comes with the expression
    type ``load`` which loads templates relative to the provided
    filename.

    Below are listed the configuration arguments specific to
    file-based templates; see the string-based template class for
    general options and documentation:

    Configuration (keyword arguments):

      ``loader_class``

        The provided class will be used to create the template loader
        object. The default implementation supports relative and
        absolute path specs.

        The class must accept keyword arguments ``search_path``
        (sequence of paths to search for relative a path spec) and
        ``default_extension`` (if provided, this should be added to
        any path spec).

      ``prepend_relative_search_path``

        Inserts the path relative to the provided template file path
        into the template search path.

        The default setting is ``True``.

      ``search_path``

        If provided, this is used as the search path for the ``load:``
        expression. It must be a string or an iterable yielding a
        sequence of strings.

    """

    expression_types = PageTemplate.expression_types.copy()
    expression_types['load'] = partial(
        ProxyExpr, '__loader',
        ignore_prefix=False
    )

    prepend_relative_search_path = True

    def __init__(self, filename, search_path=None, loader_class=TemplateLoader,
                 **config):
        if search_path is None:
            search_path = []
        else:
            if isinstance(search_path, str):
                search_path = [search_path]
            else:
                search_path = list(search_path)

        def post_init():
            # If the flag is set (this is the default), prepend the path
            # relative to the template file to the search path
            if self.prepend_relative_search_path:
                path = dirname(self.filename)
                search_path.insert(0, path)

            loader = loader_class(search_path=search_path, **config)
            template_class = type(self)

            # Bind relative template loader instance to the same template
            # class, providing the same keyword arguments.
            self._loader = loader.bind(template_class)

        super().__init__(
            filename,
            post_init_hook=post_init,
            **config
        )

    def _builtins(self):
        d = super()._builtins()
        d['__loader'] = self._loader
        return d


class PageTextTemplate(PageTemplate):
    """Text-based template class.

    Takes a non-XML input::

      template = PageTextTemplate("Hello, ${name}.")

    This is similar to the standard library class ``string.Template``,
    but uses the expression engine to substitute variables.
    """

    mode = "text"


class PageTextTemplateFile(PageTemplateFile):
    """File-based constructor."""

    mode = "text"

    def render(self, **vars):
        result = super().render(**vars)
        return result.encode(self.encoding or 'utf-8')


class Macro:
    __slots__ = "include",

    def __init__(self, render):
        self.include = render


class Macros:
    __slots__ = "template",

    def __init__(self, template):
        self.template = template

    def __getitem__(self, name):
        name = name.replace('-', '_')
        self.template.cook_check()

        try:
            function = getattr(self.template, "_render_%s" % name)
        except AttributeError:
            raise KeyError(
                "Macro does not exist: '%s'." % name)

        return Macro(function)

    @property
    def names(self):
        self.template.cook_check()

        result = []
        for name in self.template.__dict__:
            if name.startswith('_render_'):
                result.append(name[8:])
        return result
