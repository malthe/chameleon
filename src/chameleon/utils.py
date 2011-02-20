import re
import codecs

from .exc import CompilationError

try:
    import htmlentitydefs
except ImportError:
    from html import entities as htmlentitydefs

try:
    chr = unichr
except NameError:
    basestring = str
    unicode = str

encodings = {
    codecs.BOM_UTF8: 'UTF8',
    codecs.BOM_UTF16_BE: 'UTF-16BE',
    codecs.BOM_UTF16_LE: 'UTF-16LE',
    }

entity_re = re.compile(r'&(#?)(x?)(\d{1,5}|\w{1,8});')


def validate_attributes(attributes, namespace, whitelist):
    for ns, name in attributes:
        if ns == namespace and name not in whitelist:
            raise CompilationError("Bad attribute '%s' for namespace '%s'." % (
                name, ns))


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
    decoded = entity_re.subn(substitute_entity, string)[0]

    # preserve input token data
    return string.replace(string, decoded)


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

        decoded = unicode(value)
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
