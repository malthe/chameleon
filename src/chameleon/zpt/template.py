from functools import partial
from os.path import dirname

from ..i18n import fast_translate
from ..tales import TalesEngine
from ..tales import PythonExpr
from ..tales import StringExpr
from ..tales import NotExpr
from ..tales import ExistsExpr
from ..tales import ImportExpr
from ..tales import ProxyExpr
from ..tal import RepeatDict

from ..template import BaseTemplate
from ..template import BaseTemplateFile
from ..loader import TemplateLoader

from .program import MacroProgram

try:
    bytes
except NameError:
    bytes = str

try:
    str = unicode
except NameError:
    pass


class PageTemplate(BaseTemplate):
    """Template class for the Chameleon Page Templates language.

    This constructor takes a string input. To read a template source
    from a file on disk, use the file-based constructor.

    To provide a target language for translation, pass
    ``target_language`` as a keyword argument to the render method.

    The default translation function is given as a class attribute
    ``translate``. This may be overriden either on construction, or at
    render-time (in both cases, pass keyword argument ``translate``
    with a valid translation function).

    Content for substitution may be given as encoded input. To enable
    this feature, the ``encoding`` keyword argument can be passed to
    the constructor or render method. The default encoding is the
    system default --- usually ``ascii``.

    Output is always type ``unicode`` (or simply ``str`` on Python 3).
    """

    expression_types = {
        'python': PythonExpr,
        'string': StringExpr,
        'not': NotExpr,
        'exists': ExistsExpr,
        'import': ImportExpr,
        }

    default_expression = 'python'

    translate = staticmethod(fast_translate)

    encoding = None

    mode = "xml"

    def __init__(self, *args, **kwargs):
        self.macros = Macros(self)

        super(PageTemplate, self).__init__(*args, **kwargs)
        self.__dict__.update(kwargs)

    @property
    def engine(self):
        return TalesEngine(self.expression_types, self.default_expression)

    @property
    def builtins(self):
        return self._builtins()

    def parse(self, body):
        escape = True if self.mode == "xml" else False
        return MacroProgram(body, self.mode, self.filename, escape=escape)

    def render(self, encoding=None, translate=None, target_language=None, **k):
        translate = translate if translate is not None else self.translate or \
                    type(self).translate

        # Curry language parameter if non-trivial
        if target_language is not None:
            translate = partial(translate, target_language=target_language)

        encoding = encoding if encoding is not None else self.encoding
        if encoding is not None:
            txl = translate

            def translate(msgid, **kwargs):
                if isinstance(msgid, bytes):
                    msgid = str(msgid, encoding)
                return txl(msgid, **kwargs)

            def decode(inst):
                return str(inst, encoding)
        else:
            decode = str

        setdefault = k.setdefault
        setdefault("translate", translate)
        setdefault("convert", translate)
        setdefault("decode", decode)

        # Make sure we have a repeat dictionary
        if 'repeat' not in k: k['repeat'] = RepeatDict({})

        return super(PageTemplate, self).render(**k)

    def include(self, stream, econtext, rcontext):
        self.cook_check()
        self._render(stream, econtext, rcontext)

    def _builtins(self):
        return {
            'template': self,
            'macros': self.macros,
            'nothing': None,
            }


class PageTemplateFile(PageTemplate, BaseTemplateFile):
    expression_types = PageTemplate.expression_types.copy()
    expression_types['load'] = partial(ProxyExpr, '__loader')

    def _builtins(self):
        path = dirname(self.filename)
        loader = TemplateLoader(search_path=path)

        # Bind loader to same template class --- this is probably what
        # we want
        template_class = type(self)

        d = super(PageTemplateFile, self)._builtins()
        d['__loader'] = loader.bind(template_class)

        return d


class PageTextTemplate(PageTemplate):
    mode = "text"


class PageTextTemplateFile(PageTemplateFile):
    mode = "text"

    def render(self, *args, **kwargs):
        result = super(PageTextTemplateFile, self).render(*args, **kwargs)
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
