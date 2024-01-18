from __future__ import annotations

import sys
from functools import partial
from hashlib import sha256
from os.path import dirname
from typing import TYPE_CHECKING
from typing import Any
from zipfile import Path

from chameleon.astutil import Symbol
from chameleon.compiler import ExpressionEngine
from chameleon.i18n import simple_translate
from chameleon.loader import TemplateLoader
from chameleon.tal import RepeatDict
from chameleon.tales import DEFAULT_MARKER
from chameleon.tales import ExistsExpr
from chameleon.tales import ExpressionParser
from chameleon.tales import ImportExpr
from chameleon.tales import NotExpr
from chameleon.tales import ProxyExpr
from chameleon.tales import PythonExpr
from chameleon.tales import StringExpr
from chameleon.tales import StructureExpr
from chameleon.template import BaseTemplate
from chameleon.template import BaseTemplateFile
from chameleon.zpt.program import MacroProgram


if TYPE_CHECKING:
    from _typeshed import StrPath
    from collections.abc import Callable
    from collections.abc import Collection
    from collections.abc import Iterable
    from typing_extensions import Unpack

    from chameleon.types import PageTemplateConfig
    from chameleon.types import Tokenizer
    from chameleon.types import TranslationFunction


BOOLEAN_HTML_ATTRIBUTES = [
    # From http://www.w3.org/TR/xhtml1/#guidelines (C.10)
    "compact",
    "nowrap",
    "ismap",
    "declare",
    "noshade",
    "checked",
    "disabled",
    "readonly",
    "multiple",
    "selected",
    "noresize",
    "defer",
]


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

        The default setting is to autodetect if we're in HTML-mode and
        provide the standard set of boolean attributes for this
        document type.

      ``translate``

        Use this option to set a translation function.

        Example::

          def translate(msgid, domain=None, mapping=None, default=None,
                        context=None, target_language=None):
              ...
              return translation

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

    default_expression: str = 'python'
    default_content_type = 'text/html'

    translate: TranslationFunction
    if sys.version_info >= (3, 10):
        translate = staticmethod(simple_translate)
    else:
        # prior to 3.10 staticmethod is just a descriptor without a __call__
        # so it is itself not callable, we don't really care, since we only
        # ever use it as a descriptor, but to be able to override this with
        # an instance attribute we can't declare this as a descriptor and
        # since we only need this ignore in 3.9 we will get an unused ignore
        # error instead above, so we use this version check to avoid that
        translate = staticmethod(simple_translate)  # type: ignore[assignment]

    encoding: str | None = None

    boolean_attributes: Collection[str] | None = None

    mode = "xml"

    implicit_i18n_translate = False

    implicit_i18n_attributes: set[str] = set()

    trim_attribute_space = False

    enable_data_attributes = False

    enable_comment_interpolation = True

    on_error_handler: Callable[[BaseException], object] | None = None

    restricted_namespace = True

    tokenizer: Tokenizer | None = None

    default_marker = Symbol(DEFAULT_MARKER)

    # TODO: Add the documented keyword arguments
    def __init__(
        self,
        body: bytes | str,
        **config: Unpack[PageTemplateConfig]
    ):
        self.macros = Macros(self)
        super().__init__(body, **config)

    def __getitem__(self, name: str) -> Macro:
        return self.macros[name]

    @property
    def builtins(self) -> dict[str, Any]:  # type: ignore[override]
        return self._builtins()

    @property
    def engine(self) -> Callable[[], ExpressionEngine]:
        return partial(
            ExpressionEngine,
            self.expression_parser,
            default_marker=self.default_marker,
        )

    @property
    def expression_parser(self) -> ExpressionParser:
        return ExpressionParser(self.expression_types, self.default_expression)

    def parse(self, body: str) -> MacroProgram:
        boolean_attributes = self.boolean_attributes

        if self.content_type != 'text/xml':
            if boolean_attributes is None:
                boolean_attributes = BOOLEAN_HTML_ATTRIBUTES

            # In non-XML mode, we support various platform-specific
            # line endings and convert them to the UNIX newline
            # character.
            body = body.replace('\r\n', '\n').replace('\r', '\n')

        return MacroProgram(  # type: ignore[no-untyped-call]
            body, self.mode, self.filename,
            escape=True if self.mode == "xml" else False,
            default_marker=self.default_marker,
            boolean_attributes=boolean_attributes or frozenset([]),
            implicit_i18n_translate=self.implicit_i18n_translate,
            implicit_i18n_attributes=self.implicit_i18n_attributes,
            trim_attribute_space=self.trim_attribute_space,
            enable_data_attributes=self.enable_data_attributes,
            enable_comment_interpolation=self.enable_comment_interpolation,
            restricted_namespace=self.restricted_namespace,
            tokenizer=self.tokenizer
        )

    def render(self, encoding: str | None = None, **_kw: Any) -> str:
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

        translate: TranslationFunction | None = _kw.get('translate')
        if translate is None:
            translate = self.translate

            # This should not be necessary, but we include it for
            # backward compatibility.
            if translate is None:
                translate = type(self).translate

        encoding = encoding if encoding is not None else self.encoding
        if encoding is not None:
            def translate(
                msgid: str | bytes,
                txl: TranslationFunction = translate,  # type: ignore
                encoding: str = encoding,  # type: ignore[assignment]
                **kwargs: Any
            ) -> str:
                if isinstance(msgid, bytes):
                    msgid = bytes.decode(msgid, encoding)
                return txl(msgid, **kwargs)

            def decode(
                inst: bytes,
                encoding: str = encoding  # type: ignore[assignment]
            ) -> str:
                return bytes.decode(inst, encoding, 'ignore')
        else:
            decode = bytes.decode  # type: ignore[assignment]

        setdefault = _kw.setdefault
        setdefault("__translate", translate)
        setdefault("__decode", decode)
        setdefault("__on_error_handler", self.on_error_handler)
        setdefault("target_language", None)

        # Make sure we have a repeat dictionary
        if 'repeat' not in _kw:
            _kw['repeat'] = RepeatDict({})

        return super().render(**_kw)

    def include(self, *args: Any, **kwargs: Any) -> None:
        self.cook_check()
        self._render(*args, **kwargs)

    def digest(self, body: str, names: Collection[str]) -> str:
        hex = super().digest(body, names)
        if isinstance(hex, str):
            hex_b = hex.encode('utf-8')
        else:
            hex_b = hex
        digest = sha256(hex_b)
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

    def _builtins(self) -> dict[str, Any]:
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

      ``package_name``

        If provided, the template is loaded relative to the package contents.

      ``search_path``

        If provided, this is used as the search path for the ``load:``
        expression. It must be a string or an iterable yielding a
        sequence of strings.

    """

    expression_types = PageTemplate.expression_types.copy()
    expression_types['load'] = partial(  # type: ignore[assignment]
        ProxyExpr, '__loader',
        ignore_prefix=False
    )

    prepend_relative_search_path = True

    def __init__(
        self,
        filename: StrPath,
        loader_class: type[TemplateLoader] = TemplateLoader,
        package_name: str | None = None,
        search_path: Iterable[str] | str | None = None,
        **config: Unpack[PageTemplateConfig]
    ) -> None:

        if search_path is None:
            search_path = []
        else:
            # FIXME: support Path here as well?
            if isinstance(search_path, str):
                search_path = [search_path]
            else:
                search_path = list(search_path)

        def post_init() -> None:
            # If the flag is set (this is the default), prepend the path
            # relative to the template file to the search path
            if self.prepend_relative_search_path:
                path: StrPath
                if isinstance(self.filename, Path):
                    path = self.filename.parent
                else:
                    path = dirname(self.filename)
                    if package_name is not None:
                        path = "%s:%s" % (package_name, path)
                search_path.insert(0, path)  # type: ignore[arg-type]

            loader = loader_class(search_path=search_path, **config)
            template_class = type(self)

            # Bind relative template loader instance to the same template
            # class, providing the same keyword arguments.
            self._loader = loader.bind(template_class)

        # mypy correctly complains here because PageTemplate.__init__ applies
        # before BaseTemplateFile, so the signature looks incompatible
        super().__init__(  # type: ignore[call-arg]
            filename,  # type: ignore[arg-type]
            package_name=package_name,
            post_init_hook=post_init,
            **config
        )

    def _builtins(self) -> dict[str, Any]:
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

    def render(self, **vars: Any) -> bytes:  # type: ignore[override]
        result = super().render(**vars)
        return result.encode(self.encoding or 'utf-8')


class Macro:
    __slots__ = "include",

    def __init__(self, render: Callable[..., str]) -> None:
        self.include = render


class Macros:
    __slots__ = "template",

    def __init__(self, template: BaseTemplate) -> None:
        self.template = template

    def __getitem__(self, name: str) -> Macro:
        name = name.replace('-', '_')
        self.template.cook_check()

        try:
            function = getattr(self.template, "_render_%s" % name)
        except AttributeError:
            raise KeyError(
                "Macro does not exist: '%s'." % name)

        return Macro(function)

    @property
    def names(self) -> list[str]:
        self.template.cook_check()

        result = []
        for name in self.template.__dict__:
            if name.startswith('_render_'):
                result.append(name[8:])
        return result
