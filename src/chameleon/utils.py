from __future__ import annotations

import codecs
import logging
import os
import re
from enum import Enum
from html import entities as htmlentitydefs
from typing import TYPE_CHECKING
from typing import Any
from typing import Generic
from typing import Literal
from typing import NoReturn
from typing import TypeVar
from typing import overload


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from collections.abc import Sequence
    from types import TracebackType


_KT = TypeVar('_KT')
_VT_co = TypeVar('_VT_co')

log = logging.getLogger('chameleon.utils')


class _Marker(Enum):
    marker = object()


# NOTE: Enums are better markers for type narrowing
marker: Literal[_Marker.marker] = _Marker.marker


def safe_native(s: str | bytes, encoding: str = 'utf-8') -> str:
    if not isinstance(s, str):
        s = bytes.decode(s, encoding, 'replace')
    return s


def raise_with_traceback(
    exc: BaseException,
    tb: TracebackType | None
) -> NoReturn:
    exc.__traceback__ = tb
    raise exc


def encode_string(s: str) -> bytes:
    return bytes(s, 'utf-8')


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


def _has_encoding(encoding: str) -> bool:
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


def read_encoded(data: bytes) -> str:
    return read_bytes(data, "utf-8")[0]


def read_bytes(
    body: bytes,
    default_encoding: str
) -> tuple[str, str, str | None]:

    for bom, prefix, encoding in _xml_prefixes:
        if body.startswith(bom):
            document = body.decode(encoding)
            return document, encoding, \
                "text/xml" if document.startswith("<?xml") else None

        if prefix != encode_string('<?xml') and body.startswith(prefix):
            return body.decode(encoding), encoding, "text/xml"

    content_type: str | None
    if body.startswith(_xml_decl):
        content_type = "text/xml"
        encoding = read_xml_encoding(body) or default_encoding
    else:
        content_type, encoding = detect_encoding(body, default_encoding)

    return body.decode(encoding), encoding, content_type


def detect_encoding(
    body: str | bytes,
    default_encoding: str
) -> tuple[str | None, str]:

    if not isinstance(body, str):
        body = body.decode('ascii', 'ignore')

    match = RE_META.search(body)
    if match is not None:
        # this can be treated like tuple[str, str] since we unpack it
        return match.groups()  # type: ignore[return-value]

    return None, default_encoding


def read_xml_encoding(body: bytes) -> str | None:
    if body.startswith(b'<?xml'):
        match = RE_ENCODING.search(body)
        if match is not None:
            return match.group('encoding').decode('ascii')
    return None


def mangle(filename: str) -> str:
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


def char2entity(c: str | bytes | bytearray) -> str:
    cp = ord(c)
    name = htmlentitydefs.codepoint2name.get(cp)
    return '&%s;' % name if name is not None else '&#%d;' % cp


def substitute_entity(
    match: re.Match[str],
    n2cp: Mapping[str, int] = htmlentitydefs.name2codepoint
) -> str:
    ent = match.group(3)

    if match.group(1) == "#":
        if match.group(2) == '':
            return chr(int(ent))
        elif match.group(2) == 'x':
            return chr(int('0x' + ent, 16))
        else:
            # FIXME: This should be unreachable, so we can
            #        try raising an AssertionError instead
            return ''
    else:
        cp = n2cp.get(ent)

        if cp:
            return chr(cp)
        else:
            return match.group()


def create_formatted_exception(
    exc: BaseException,
    cls: type[object],
    formatter: Callable[..., str],
    base: type[BaseException] = Exception
) -> BaseException:
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

        inst: BaseException
        try:
            inst = BaseException.__new__(new)
        except TypeError:
            inst = cls.__new__(new)

        BaseException.__init__(inst, *exc.args)
        inst.__dict__ = exc.__dict__  # type: ignore[attr-defined]

        return inst
    except ValueError:
        name = type(exc).__name__
        log.warn("Unable to copy exception of type '%s'." % name)
        raise TypeError(exc)


_concat = "".join


def join(stream: Iterable[str]) -> str:
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


def decode_htmlentities(string: str) -> str:
    """
    >>> str(decode_htmlentities('&amp;amp;'))
    '&amp;'

    """

    decoded = entity_re.subn(substitute_entity, string)[0]

    # preserve input token data
    return string.replace(string, decoded)


# Taken from zope.dottedname
def _resolve_dotted(name: str, module: str | None = None) -> Any:
    name_parts = name.split('.')
    if not name_parts[0]:
        if module is None:
            raise ValueError("relative name without base module")
        module_parts = module.split('.')
        name_parts.pop(0)
        while not name[0]:
            module_parts.pop()
            name_parts.pop(0)
        name_parts = module_parts + name_parts

    used = name_parts.pop(0)
    found = __import__(used)
    for n in name_parts:
        used += '.' + n
        try:
            found = getattr(found, n)
        except AttributeError:
            __import__(used)
            found = getattr(found, n)

    return found


def resolve_dotted(dotted: str) -> Any:
    if dotted not in module_cache:
        resolved = _resolve_dotted(dotted)
        module_cache[dotted] = resolved
    return module_cache[dotted]


def limit_string(s: str, max_length: int = 53) -> str:
    if len(s) > max_length:
        return s[:max_length - 3] + '...'

    return s


def value_repr(value: object) -> str:
    if isinstance(value, str):
        short = limit_string(value)
        return short.replace('\n', '\\n')
    if isinstance(value, (int, float)):
        return value  # type: ignore[return-value]
    if isinstance(value, dict):
        return '{...} (%d)' % len(value)

    try:
        # FIXME: Is this trailing comma intentional?
        #        it changes the formatting <foo (bar,) at ...>
        #        vs. <foo bar at ...>
        name = str(getattr(value, '__name__', None)),
    except:  # noqa: E722 do not use bare 'except'
        name = '-'  # type: ignore[assignment]

    return '<{} {} at {}>'.format(
        type(value).__name__, name, hex(abs(id(value))))


class callablestr(str):
    __slots__ = ()

    def __call__(self) -> str:
        return self


class callableint(int):
    __slots__ = ()

    def __call__(self) -> int:
        return self


class descriptorstr:
    __slots__ = "function", "__name__"

    def __init__(self, function: Callable[[Any], str]) -> None:
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context: object, cls: type[object]) -> callablestr:
        return callablestr(self.function(context))


class descriptorint:
    __slots__ = "function", "__name__"

    def __init__(self, function: Callable[[Any], int]) -> None:
        self.function = function
        self.__name__ = function.__name__

    def __get__(self, context: object, cls: type[object]) -> callableint:
        return callableint(self.function(context))


class DebuggingOutputStream(list[str]):
    def append(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(value)
        super().append(value)


class Scope(dict[str, Any]):
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

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, marker)
        if value is marker:
            raise KeyError(key)
        return value

    def __contains__(self, key: object) -> bool:
        return self.get(key, marker) is not marker  # type: ignore

    def __iter__(self) -> Iterator[str]:
        root = getattr(self, "_root", marker)
        yield from super().__iter__()
        if root is not marker:
            for key in root:
                if not super().__contains__(key):
                    yield key

    @overload
    def get(self, key: str, default: None = None) -> Any | None: ...
    @overload
    def get(self, key: str, default: object) -> Any: ...

    def get(self, key: str, default: object = None) -> Any:
        value = super().get(key, marker)
        if value is not marker:
            return value

        root = getattr(self, "_root", marker)
        if root is not marker:
            value = super(Scope, root).get(key, marker)

            if value is not marker:
                return value

        return default

    @property
    def vars(self) -> Mapping[str, Any]:
        return self

    def copy(self) -> Scope:
        inst = Scope(self)
        root = getattr(self, "_root", self)
        inst._root = root  # type: ignore[attr-defined]
        return inst

    def set_global(self, name: str, value: Any) -> None:
        root = getattr(self, "_root", self)
        root[name] = value

    def get_name(self, key: str) -> Any:
        value = self.get(key, marker)
        if value is marker:
            raise NameError(key)
        return value

    setLocal = set_local
    setGlobal = set_global


class ListDictProxy(Generic[_KT, _VT_co]):
    def __init__(
        self: ListDictProxy[_KT, _VT_co],
        _l: Sequence[Mapping[_KT, _VT_co]]
    ) -> None:
        self._l = _l

    def get(self, key: _KT) -> _VT_co | None:
        return self._l[-1].get(key)


class Markup(str):
    """Wraps a string to always render as structure.

    >>> Markup('<br />')
    s'<br />'
    """

    def __html__(self) -> str:
        return str(self)

    def __repr__(self) -> str:
        return "s'%s'" % self


class ImportableMarker:
    def __init__(self, module: str, name: str) -> None:
        self.__module__ = module
        self.name = name

    @property
    def __name__(self) -> str:
        return "%s_MARKER" % self.name

    def __repr__(self) -> str:
        return '<%s>' % self.name


def lookup_attr(obj: object, key: str) -> Any:
    try:
        return getattr(obj, key)
    except AttributeError as exc:
        # FIXME: What are the two try excepts here for?
        #        We just raise the thing we catch...
        try:
            get = obj.__getitem__  # type: ignore[index]
        except AttributeError:
            raise exc
        try:
            return get(key)
        except KeyError:
            raise exc
