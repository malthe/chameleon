import os
import re
import sys
import codecs
import logging

from copy import copy

version = sys.version_info[:3]

try:
    import ast as _ast
except ImportError:
    from chameleon import ast25 as _ast


class ASTProxy(object):
    aliases = {
        # Python 3.3
        'TryExcept': 'Try',
        'TryFinally': 'Try',
        }

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return _ast.__dict__.get(name) or getattr(_ast, self.aliases[name])


ast = ASTProxy()

log = logging.getLogger('chameleon.utils')

# Python 2
if version < (3, 0, 0):
    import htmlentitydefs
    import __builtin__ as builtins

    from .py25 import raise_with_traceback

    chr = unichr
    native_string = str
    decode_string = unicode
    encode_string = str
    unicode_string = unicode
    string_type = basestring
    byte_string = str

    def safe_native(s, encoding='utf-8'):
        if not isinstance(s, unicode):
            s = decode_string(s, encoding, 'replace')

        return s.encode(encoding)

# Python 3
else:
    from html import entities as htmlentitydefs
    import builtins

    byte_string = bytes
    string_type = str
    native_string = str
    decode_string = bytes.decode
    encode_string = lambda s: bytes(s, 'utf-8')
    unicode_string = str

    def safe_native(s, encoding='utf-8'):
        if not isinstance(s, str):
            s = decode_string(s, encoding, 'replace')

        return s

    def raise_with_traceback(exc, tb):
        exc.__traceback__ = tb
        raise exc

def text_(s, encoding='latin-1', errors='strict'):
    """ If ``s`` is an instance of ``byte_string``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``"""
    if isinstance(s, byte_string):
        return s.decode(encoding, errors)
    return s

entity_re = re.compile(r'&(#?)(x?)(\d{1,5}|\w{1,8});')

module_cache = {}

xml_prefixes = (
    (codecs.BOM_UTF8, 'utf-8-sig'),
    (codecs.BOM_UTF16_BE, 'utf-16-be'),
    (codecs.BOM_UTF16_LE, 'utf-16-le'),
    (codecs.BOM_UTF16, 'utf-16'),
    (codecs.BOM_UTF32_BE, 'utf-32-be'),
    (codecs.BOM_UTF32_LE, 'utf-32-le'),
    (codecs.BOM_UTF32, 'utf-32'),
    )


def _has_encoding(encoding):
    try:
        "".encode(encoding)
    except LookupError:
        return False
    else:
        return True


# Precomputed prefix table
_xml_prefixes = tuple(
    (bom, str('<?xml').encode(encoding), encoding)
    for bom, encoding in reversed(xml_prefixes)
    if _has_encoding(encoding)
    )

_xml_decl = encode_string("<?xml")

RE_META = re.compile(
    r'\s*<meta\s+http-equiv=["\']?Content-Type["\']?'
    r'\s+content=["\']?([^;]+);\s*charset=([^"\']+)["\']?\s*/?\s*>\s*',
    re.IGNORECASE
    )

RE_ENCODING = re.compile(
    r'encoding\s*=\s*(?:"|\')(?P<encoding>[\w\-]+)(?:"|\')'.encode('ascii'),
    re.IGNORECASE
    )


def read_encoded(data):
    return read_bytes(data, "utf-8")[0]


def read_bytes(body, default_encoding):
    for bom, prefix, encoding in _xml_prefixes:
        if body.startswith(bom):
            document = body.decode(encoding)
            return document, encoding, \
                   "text/xml" if document.startswith("<?xml") else None

        if prefix != encode_string('<?xml') and body.startswith(prefix):
            return body.decode(encoding), encoding, "text/xml"

    if body.startswith(_xml_decl):
        content_type = "text/xml"

        encoding = read_xml_encoding(body) or default_encoding
    else:
        content_type, encoding = detect_encoding(body, default_encoding)

    return body.decode(encoding), encoding, content_type


def detect_encoding(body, default_encoding):
    if not isinstance(body, str):
        body = body.decode('ascii', 'ignore')

    match = RE_META.search(body)
    if match is not None:
        return match.groups()

    return None, default_encoding


def read_xml_encoding(body):
    if body.startswith('<?xml'.encode('ascii')):
        match = RE_ENCODING.search(body)
        if match is not None:
            return match.group('encoding').decode('ascii')


def mangle(filename):
    """Mangles template filename into top-level Python module name.

    >>> mangle('hello_world.pt')
    'hello_world'

    >>> mangle('foo.bar.baz.pt')
    'foo_bar_baz'

    >>> mangle('foo-bar-baz.pt')
    'foo_bar_baz'

    """

    base, ext = os.path.splitext(filename)
    return base.replace('.', '_').replace('-', '_')


def char2entity(c):
    cp = ord(c)
    name = htmlentitydefs.codepoint2name.get(cp)
    return '&%s;' % name if name is not None else '&#%d;' % cp


def substitute_entity(match, n2cp=htmlentitydefs.name2codepoint):
    ent = match.group(3)

    if match.group(1) == "#":
        if match.group(2) == '':
            return chr(int(ent))
        elif match.group(2) == 'x':
            return chr(int('0x' + ent, 16))
    else:
        cp = n2cp.get(ent)

        if cp:
            return chr(cp)
        else:
            return match.group()


def create_formatted_exception(exc, cls, formatter, base=Exception):
    try:
        try:
            new = type(cls.__name__, (cls, base), {
                '__str__': formatter,
                '__new__': BaseException.__new__,
                '__module__': cls.__module__,
                })
        except TypeError:
            new = cls

        try:
            inst = BaseException.__new__(new)
        except TypeError:
            inst = cls.__new__(new)

        BaseException.__init__(inst, *exc.args)
        inst.__dict__ = exc.__dict__

        return inst
    except ValueError:
        name = type(exc).__name__
        log.warn("Unable to copy exception of type '%s'." % name)
        raise TypeError(exc)


def unescape(string):
    for name in ('lt', 'gt', 'quot'):
        cp = htmlentitydefs.name2codepoint[name]
        string = string.replace('&%s;' % name, chr(cp))

    return string


_concat = unicode_string("").join


def join(stream):
    """Concatenate stream.

    >>> print(join(('Hello', ' ', 'world')))
    Hello world

    >>> join(('Hello', 0))
    Traceback (most recent call last):
     ...
    TypeError: ... expected ...

    """

    try:
        return _concat(stream)
    except:
        # Loop through stream and coerce each element into unicode;
        # this should raise an exception
        for element in stream:
            unicode_string(element)

        # In case it didn't, re-raise the original exception
        raise


def decode_htmlentities(string):
    """
    >>> native_string(decode_htmlentities('&amp;amp;'))
    '&amp;'

    """

    decoded = entity_re.subn(substitute_entity, string)[0]

    # preserve input token data
    return string.replace(string, decoded)


# Taken from zope.dottedname
def _resolve_dotted(name, module=None):
    name = name.split('.')
    if not name[0]:
        if module is None:
            raise ValueError("relative name without base module")
        module = module.split('.')
        name.pop(0)
        while not name[0]:
            module.pop()
            name.pop(0)
        name = module + name

    used = name.pop(0)
    found = __import__(used)
    for n in name:
        used += '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            __import__(used)
            found = getattr(found, n)

    return found


def resolve_dotted(dotted):
    if not dotted in module_cache:
        resolved = _resolve_dotted(dotted)
        module_cache[dotted] = resolved
    return module_cache[dotted]


def limit_string(s, max_length=53):
    if len(s) > max_length:
        return s[:max_length - 3] + '...'

    return s


def format_kwargs(kwargs):
    items = []
    for name, value in kwargs.items():
        if isinstance(value, string_type):
            short = limit_string(value)
            items.append((name, short.replace('\n', '\\n')))
        elif isinstance(value, (int, float)):
            items.append((name, value))
        elif isinstance(value, dict):
            items.append((name, '{...} (%d)' % len(value)))
        else:
            items.append((name,
                "<%s %s at %s>" % (
                    type(value).__name__,
                    getattr(value, '__name__', "-"),
                    hex(abs(id(value))))))

    return ["%s: %s" % item for item in items]


class callablestr(str):
    __slots__ = ()

    def __call__(self):
        return self


class callableint(int):
    __slots__ = ()

    def __call__(self):
        return self


class descriptorstr(object):
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callablestr(self.function(context))


class descriptorint(object):
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callableint(self.function(context))


class DebuggingOutputStream(list):
    def append(self, value):
        if not isinstance(value, string_type):
            raise TypeError(value)

        unicode_string(value)
        list.append(self, value)


class Scope(dict):
    set_local = setLocal = dict.__setitem__

    __slots__ = "set_global",

    def __new__(cls, *args):
        inst = dict.__new__(cls, *args)
        inst.set_global = inst.__setitem__
        return inst

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            raise NameError(key)

    @property
    def vars(self):
        return self

    def copy(self):
        inst = Scope(self)
        inst.set_global = self.set_global
        return inst


class ListDictProxy(object):
    def __init__(self, l):
        self._l = l

    def get(self, key):
        return self._l[-1].get(key)


class Markup(unicode_string):
    """Wraps a string to always render as structure.

    >>> Markup('<br />')
    s'<br />'
    """

    def __html__(self):
        return unicode_string(self)

    def __repr__(self):
        return "s'%s'" % self
