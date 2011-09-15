import os
import re
import codecs

try:
    import htmlentitydefs
except ImportError:
    from html import entities as htmlentitydefs

try:
    chr = unichr
    native = str
    decode_string = unicode

    def safe_native(s, encoding='utf-8'):
        if not isinstance(s, unicode):
            s = decode_string(s, encoding, 'replace')

        return s.encode(encoding)
except NameError:
    decode_string = bytes.decode
    basestring = str
    unicode = str
    native = str

    def safe_native(s, encoding='utf-8'):
        if not isinstance(s, str):
            s = decode_string(s, encoding, 'replace')

        return s


encodings = {
    codecs.BOM_UTF8: 'UTF8',
    codecs.BOM_UTF16_BE: 'UTF-16BE',
    codecs.BOM_UTF16_LE: 'UTF-16LE',
    }

entity_re = re.compile(r'&(#?)(x?)(\d{1,5}|\w{1,8});')

module_cache = {}


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


def read_bom(source):
    for bom, encoding in encodings.items():
        if source.startswith(bom):
            return bom


def decode(source):
    bom = read_bom(source)
    if bom is not None:
        encoding = encodings[bom]
        source = source[len(bom):]
    else:
        encoding = 'utf-8'
    return bom, source, encoding


def read_encoded(source):
    bom, body, encoding = decode(source)
    return body.decode(encoding)


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


def derive_formatted_exception(exc, cls, formatter):
    try:
        new = type(cls.__name__, (cls, Exception), {
            '__str__': formatter,
            })
        exc.__class__ = new
    except TypeError:
        d = exc.__dict__
        exc = cls.__new__(new)
        exc.__dict__ = d

    return exc


def unescape(string):
    for name in ('lt', 'gt', 'quot'):
        cp = htmlentitydefs.name2codepoint[name]
        string = string.replace('&%s;' % name, chr(cp))

    return string


_concat = "".join


def join(stream):
    """Concatenate stream.

    >>> join(('Hello', ' ', 'world'))
    'Hello world'

    >>> join(('Hello', 0))
    Traceback (most recent call last):
     ...
    TypeError: ... int ...

    """

    try:
        return _concat(stream)
    except:
        # Loop through stream and coerce each element into unicode;
        # this should raise an exception
        for element in stream:
            unicode(element)

        # In case it didn't, re-raise the original exception
        raise


def decode_htmlentities(string):
    """
    >>> native(decode_htmlentities('&amp;amp;'))
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
        if isinstance(value, (native, unicode)):
            short = limit_string(value)
            items.append((name, short.replace('\n', '\\n')))
        elif isinstance(value, (int, float, basestring)):
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
        if not isinstance(value, basestring):
            raise TypeError(value)

        unicode(value)
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
