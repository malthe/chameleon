import codecs
import logging
import os
import re
from html import entities as htmlentitydefs


log = logging.getLogger('chameleon.utils')
marker = object()


def safe_native(s, encoding='utf-8'):
    if not isinstance(s, str):
        s = bytes.decode(s, encoding, 'replace')
    return s


def raise_with_traceback(exc, tb):
    exc.__traceback__ = tb
    raise exc


def encode_string(s):
    return bytes(s, 'utf-8')


def text_(s, encoding='latin-1', errors='strict'):
    """ If ``s`` is an instance of ``bytes``, return
    ``s.decode(encoding, errors)``, otherwise return ``s``"""
    if isinstance(s, bytes):
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
    (bom, '<?xml'.encode(encoding), encoding)
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
    br'encoding\s*=\s*(?:"|\')(?P<encoding>[\w\-]+)(?:"|\')',
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
    if body.startswith(b'<?xml'):
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
                '_original__str__': exc.__str__,
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


_concat = "".join


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
    except BaseException:
        # Loop through stream and coerce each element into unicode;
        # this should raise an exception
        for element in stream:
            str(element)

        # In case it didn't, re-raise the original exception
        raise


def decode_htmlentities(string):
    """
    >>> str(decode_htmlentities('&amp;amp;'))
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
    if dotted not in module_cache:
        resolved = _resolve_dotted(dotted)
        module_cache[dotted] = resolved
    return module_cache[dotted]


def limit_string(s, max_length=53):
    if len(s) > max_length:
        return s[:max_length - 3] + '...'

    return s


def value_repr(value):
    if isinstance(value, str):
        short = limit_string(value)
        return short.replace('\n', '\\n')
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return '{...} (%d)' % len(value)

    try:
        name = str(getattr(value, '__name__', None)),
    except:  # noqa: E722 do not use bare 'except'
        name = '-'

    return '<{} {} at {}>'.format(
        type(value).__name__, name, hex(abs(id(value))))


class callablestr(str):
    __slots__ = ()

    def __call__(self):
        return self


class callableint(int):
    __slots__ = ()

    def __call__(self):
        return self


class descriptorstr:
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callablestr(self.function(context))


class descriptorint:
    __slots__ = "function", "__name__"

    def __init__(self, function):
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context, cls):
        return callableint(self.function(context))


class DebuggingOutputStream(list):
    def append(self, value):
        if not isinstance(value, str):
            raise TypeError(value)

        str(value)
        list.append(self, value)


class Scope(dict):
    """
    >>> scope = Scope()
    >>> scope['a'] = 1
    >>> copy = scope.copy()

    Setting a local value and then a global value, we expect the local value
    to take precedence.

    >>> copy['a'] = 2
    >>> copy.set_global('a', 3)
    >>> assert copy['a'] == 2

    However, setting a new global value should be immediately visible.

    >>> copy.set_global('b', 1)
    >>> assert copy['b'] == 1

    Make sure the objects are reference-counted, not requiring a full
    collection to be disposed of.

    >>> import gc
    >>> _ = gc.collect()
    >>> del copy
    >>> del scope
    >>> import platform
    >>> assert gc.collect() == (
    ...     0 if platform.python_implementation() == 'CPython' else None
    ... )
    """

    __slots__ = "_root",

    set_local = dict.__setitem__

    def __getitem__(self, key):
        value = self.get(key, marker)
        if value is marker:
            raise KeyError(key)
        return value

    def __contains__(self, key):
        return self.get(key, marker) is not marker

    def get(self, key, default=None):
        value = dict.get(self, key, marker)
        if value is not marker:
            return value

        root = getattr(self, "_root", marker)
        if root is not marker:
            value = dict.get(root, key, marker)

            if value is not marker:
                return value

        return default

    def items(self):
        raise NotImplementedError()

    def keys(self):
        raise NotImplementedError()

    def values(self):
        raise NotImplementedError()

    @property
    def vars(self):
        return self

    def copy(self):
        inst = Scope(self)
        root = getattr(self, "_root", self)
        inst._root = root
        return inst

    def set_global(self, name, value):
        root = getattr(self, "_root", self)
        root[name] = value

    def get_name(self, key):
        value = self.get(key, marker)
        if value is marker:
            raise NameError(key)
        return value

    setLocal = set_local
    setGlobal = set_global


class ListDictProxy:
    def __init__(self, _l):
        self._l = _l

    def get(self, key):
        return self._l[-1].get(key)


class Markup(str):
    """Wraps a string to always render as structure.

    >>> Markup('<br />')
    s'<br />'
    """

    def __html__(self):
        return str(self)

    def __repr__(self):
        return "s'%s'" % self


class ImportableMarker:
    def __init__(self, module, name):
        self.__module__ = module
        self.name = name

    @property
    def __name__(self):
        return "%s_MARKER" % self.name

    def __repr__(self):
        return '<%s>' % self.name


def lookup_attr(obj, key):
    try:
        return getattr(obj, key)
    except AttributeError as exc:
        try:
            get = obj.__getitem__
        except AttributeError:
            raise exc
        try:
            return get(key)
        except KeyError:
            raise exc
