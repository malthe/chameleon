try:
    import ast
except ImportError:
    from chameleon import ast24 as ast

from functools import partial
from os.path import dirname

from ..i18n import fast_translate
from ..tales import PythonExpr
from ..tales import StringExpr
from ..tales import NotExpr
from ..tales import ExistsExpr
from ..tales import ImportExpr
from ..tales import ProxyExpr
from ..tales import StructureExpr
from ..tales import ExpressionParser

from ..tal import RepeatDict

from ..template import BaseTemplate
from ..template import BaseTemplateFile
from ..compiler import ExpressionEngine
from ..loader import TemplateLoader
from ..astutil import Builtin
from ..utils import decode_string
from ..utils import string_type

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

      ``default_expression``

        Set the default expression type. The default setting is
        ``python``.

      ``encoding``

        The default text substitution value is a unicode string on
        Python 2 or simply string on Python 3.

        Pass an encoding to allow encoded byte string input
        (e.g. UTF-8).

      ``literal_false``

        Attributes are not dropped for a value of ``False``. Instead,
        the value is coerced to a string.

        This setting exists to provide compatibility with the
        reference implementation.

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

          def translate(msgid, domain=None, mapping=None, default=None):
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

      ``strict``

        Enabled by default. If disabled, expressions are only required
        to be valid at evaluation time.

        This setting exists to provide compatibility with the
        reference implementation which compiles expressions at
        evaluation time.

      ``trim_attribute_space``

        If set, additional attribute whitespace will be stripped.

    Output is unicode on Python 2 and string on Python 3.
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

    translate = staticmethod(fast_translate)

    encoding = None

    boolean_attributes = set()

    literal_false = False

    mode = "xml"

    implicit_i18n_translate = False

    implicit_i18n_attributes = set()

    trim_attribute_space = False

    def __init__(self, body, **config):
        self.macros = Macros(self)
        super(PageTemplate, self).__init__(body, **config)

    def __getitem__(self, name):
        return self.macros[name]

    @property
    def builtins(self):
        return self._builtins()

    @property
    def engine(self):
        if self.literal_false:
            default_marker = ast.Str(s="__default__")
        else:
            default_marker = Builtin("False")

        return partial(
            ExpressionEngine,
            self.expression_parser,
            default_marker=default_marker,
            )

    @property
    def expression_parser(self):
        return ExpressionParser(self.expression_types, self.default_expression)

    def parse(self, body):
        if self.literal_false:
            default_marker = ast.Str(s="__default__")
        else:
            default_marker = Builtin("False")

        return MacroProgram(
            body, self.mode, self.filename,
            escape=True if self.mode == "xml" else False,
            default_marker=default_marker,
            boolean_attributes=self.boolean_attributes,
            implicit_i18n_translate=self.implicit_i18n_translate,
            implicit_i18n_attributes=self.implicit_i18n_attributes,
            trim_attribute_space=self.trim_attribute_space,
            )

    def render(self, encoding=None, translate=None, target_language=None, **vars):
        """Render template to string.

        The ``encoding`` and ``translate`` arguments are documented in
        the template class constructor. If passed to this method, they
        are used instead of the class defaults.

        Additional arguments:

          ``target_language``

            This argument will be partially applied to the translation
            function.

            An alternative is thus to simply provide a custom
            translation function which includes this information or
            relies on a different mechanism.

        """

        non_trivial_translate = translate is not None
        translate = translate if non_trivial_translate else self.translate or \
                    type(self).translate

        # Curry language parameter if non-trivial
        if target_language is not None:
            translate = partial(translate, target_language=target_language)

        encoding = encoding if encoding is not None else self.encoding
        if encoding is not None:
            txl = translate

            def translate(msgid, **kwargs):
                if isinstance(msgid, bytes):
                    msgid = decode_string(msgid, encoding)
                return txl(msgid, **kwargs)

            def decode(inst):
                return decode_string(inst, encoding, 'ignore')
        else:
            decode = decode_string

        setdefault = vars.setdefault
        setdefault("__translate", translate)
        setdefault("__convert", translate)
        setdefault("__decode", decode)

        if non_trivial_translate:
            vars['translate'] = translate

        # Make sure we have a repeat dictionary
        if 'repeat' not in vars: vars['repeat'] = RepeatDict({})

        return super(PageTemplate, self).render(**vars)

    def include(self, *args, **kwargs):
        self.cook_check()
        self._render(*args, **kwargs)

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
    expression_types['load'] = partial(ProxyExpr, '__loader')

    prepend_relative_search_path = True

    def __init__(self, filename, search_path=None, loader_class=TemplateLoader,
                 **config):
        super(PageTemplateFile, self).__init__(filename, **config)

        if search_path is None:
            search_path = []
        else:
            if isinstance(search_path, string_type):
                search_path = [search_path]
            else:
                search_path = list(search_path)

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

    def _builtins(self):
        d = super(PageTemplateFile, self)._builtins()
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
        result = super(PageTextTemplateFile, self).render(**vars)
        return result.encode(self.encoding or 'utf-8')


class Macro(object):
    __slots__ = "include",

    def __init__(self, render):
        self.include = render


class Macros(object):
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
