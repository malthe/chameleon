from ..i18n import fast_translate
from ..tales import TalesEngine
from ..tales import PythonExpr
from ..tales import StringExpr
from ..tales import NotExpr
from ..tales import ExistsExpr
from ..tales import ImportExpr
from ..tal import RepeatDict

from ..template import BaseTemplate
from ..template import BaseTemplateFile

from .program import MacroProgram as Program

try:
    str = unicode
except NameError:
    pass


class PageTemplate(BaseTemplate):
    """Zope Page Templates.

    To provide a custom translation function, use the ``translate``
    parameter.

    This template class supports encoded input. The default is
    ``'ascii'``, but an alternative encoding may be provided as
    ``encoding``. Note that output is always unicode.

    The ``convert`` parameter specifies a function used to convert a
    non-string value to string. Similarly, ``decode`` is used to
    decode an encoded string to a native string (the default is to use
    coercion, which relies on the program's default encoding --
    usually ``'ascii'``).
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

    convert = None

    decode = str

    encoding = None

    mode = "xml"

    def __init__(self, *args, **kwargs):
        super(PageTemplate, self).__init__(*args, **kwargs)
        self.__dict__.update(kwargs)
        self.macros = Macros(self)

    @property
    def engine(self):
        return TalesEngine(self.expression_types, self.default_expression)

    def parse(self, body):
        escape = True if self.mode == "xml" else False
        return Program(body, self.mode, self.filename, escape=escape)

    def render(self, translate=None, convert=None, decode=None, **kwargs):
        translate = translate if translate is not None else self.translate
        convert = convert if convert is not None else translate
        decode = decode if decode is not None else self.decode
        encoding = self.encoding

        if encoding is not None:
            def translate(msgid, translate=translate, **kwargs):
                if isinstance(msgid, bytes):
                    msgid = str(msgid, encoding)
                return translate(msgid, **kwargs)

            def decode(inst):
                return str(inst, encoding)

        setdefault = kwargs.setdefault

        setdefault("template", self)
        setdefault("macros", self.macros)
        setdefault("repeat", RepeatDict())
        setdefault("translate", translate)
        setdefault("convert", convert)
        setdefault("decode", decode)
        setdefault("nothing", None)

        return super(PageTemplate, self).render(**kwargs)

    def include(self, stream, econtext, rcontext):
        self.cook_check()
        self._render(stream, econtext, rcontext)


class PageTemplateFile(PageTemplate, BaseTemplateFile):
    pass


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
