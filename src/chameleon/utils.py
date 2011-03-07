import re
import codecs

try:
    import htmlentitydefs
except ImportError:
    from html import entities as htmlentitydefs

try:
    chr = unichr
    native = str
except NameError:
    basestring = str
    unicode = str
    native = str

encodings = {
    codecs.BOM_UTF8: 'UTF8',
    codecs.BOM_UTF16_BE: 'UTF-16BE',
    codecs.BOM_UTF16_LE: 'UTF-16LE',
    }

entity_re = re.compile(r'&(#?)(x?)(\d{1,5}|\w{1,8});')

module_cache = {}


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


def format_kwargs(kwargs):
    items = []
    for name, value in kwargs.items():
        if isinstance(value, (int, float, basestring)):
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


class Placeholder(object):
    def __str__(self):
        raise RuntimeError("Evaluation of symbolic value disallowed.")


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
