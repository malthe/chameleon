##############################################################################
#
# Copyright (c) 2001, 2002 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import copy
import re

from .exc import LanguageError
from .namespaces import XMLNS_NS
from .parser import groups
from .utils import descriptorint
from .utils import descriptorstr


try:
    # optional library: `zope.interface`
    import zope.interface

    from chameleon import interfaces
except ImportError:
    interfaces = None


NAME = r"[a-zA-Z_][-a-zA-Z0-9_]*"
DEFINE_RE = re.compile(
    r"(?s)\s*(?:(global|local)\s+)?" +
    r"({}|\({}(?:,\s*{})*\))\s+(.*)\Z".format(NAME, NAME, NAME),
    re.UNICODE)
SUBST_RE = re.compile(r"\s*(?:(text|structure)\s+)?(.*)\Z", re.S | re.UNICODE)
ATTR_RE = re.compile(r"\s*([^\s{}'\"]+)\s+([^\s].*)\Z", re.S | re.UNICODE)

ENTITY_RE = re.compile(r'(&(#?)(x?)(\d{1,5}|\w{1,8});)')

WHITELIST = frozenset([
    "define",
    "comment",
    "condition",
    "content",
    "replace",
    "repeat",
    "attributes",
    "on-error",
    "omit-tag",
    "script",
    "switch",
    "case",
    "xmlns",
    "xml"
])


def split_parts(arg):
    # Break in pieces at undoubled semicolons and
    # change double semicolons to singles:
    i = 0
    while i < len(arg):
        m = ENTITY_RE.search(arg[i:])
        if m is None:
            break
        arg = arg[:i + m.end()] + ';' + arg[i + m.end():]
        i += m.end()

    arg = arg.replace(";;", "\0")
    parts = arg.split(';')
    parts = [p.replace("\0", ";") for p in parts]
    if len(parts) > 1 and not parts[-1].strip():
        del parts[-1]  # It ended in a semicolon

    return parts


def parse_attributes(clause):
    attrs = []
    seen = set()
    for part in split_parts(clause):
        m = ATTR_RE.match(part)
        if not m:
            name, expr = None, part.strip()
        else:
            name, expr = groups(m, part)

        if name in seen:
            raise LanguageError(
                "Duplicate attribute name in attributes.", part)

        seen.add(name)
        attrs.append((name, expr))

    return attrs


def parse_substitution(clause):
    m = SUBST_RE.match(clause)
    if m is None:
        raise LanguageError(
            "Invalid content substitution syntax.", clause)

    key, expression = groups(m, clause)
    if not key:
        key = "text"

    return key, expression


def parse_defines(clause):
    """
    Parses a tal:define value.

    # Basic syntax, implicit local
    >>> parse_defines('hello lovely')
    [('local', ('hello',), 'lovely')]

    # Explicit local
    >>> parse_defines('local hello lovely')
    [('local', ('hello',), 'lovely')]

    # With global
    >>> parse_defines('global hello lovely')
    [('global', ('hello',), 'lovely')]

    # Multiple expressions
    >>> parse_defines('hello lovely; tea time')
    [('local', ('hello',), 'lovely'), ('local', ('tea',), 'time')]

    # With multiple names
    >>> parse_defines('(hello, howdy) lovely')
    [('local', ['hello', 'howdy'], 'lovely')]

    # With unicode whitespace
    >>> try:
    ...     s = '\xc2\xa0hello lovely'.decode('utf-8')
    ... except AttributeError:
    ...     s = '\xa0hello lovely'
    >>> parse_defines(s) == [
    ...     ('local', ('hello',), 'lovely')
    ... ]
    True

    """
    defines = []
    for part in split_parts(clause):
        m = DEFINE_RE.match(part)
        if m is None:
            raise LanguageError("Invalid define syntax", part)
        context, name, expr = groups(m, part)
        context = context or "local"

        if name.startswith('('):
            names = [n.strip() for n in name.strip('()').split(',')]
        else:
            names = (name,)

        defines.append((context, names, expr))

    return defines


def prepare_attributes(attrs, dyn_attributes, i18n_attributes,
                       ns_attributes, drop_ns):
    drop = {attribute['name']
            for attribute, (ns, value) in zip(attrs, ns_attributes)
            if ns in drop_ns or (
                ns == XMLNS_NS and
                attribute['value'] in drop_ns)}

    attributes = []
    normalized = {}

    for attribute in attrs:
        name = attribute['name']

        if name in drop:
            continue

        attributes.append((
            name,
            attribute['value'],
            attribute['quote'],
            attribute['space'],
            attribute['eq'],
            None,
        ))

        normalized[name.lower()] = len(attributes) - 1

    for name, expr in dyn_attributes:
        index = normalized.get(name.lower()) if name else None

        if index is not None:
            _, text, quote, space, eq, _ = attributes[index]
            add = attributes.__setitem__
        else:
            text = None
            quote = '"'
            space = " "
            eq = "="
            index = len(attributes)
            add = attributes.insert
            if name is not None:
                normalized[name.lower()] = len(attributes) - 1

        attribute = name, text, quote, space, eq, expr
        add(index, attribute)

    for name in i18n_attributes:
        attr = name.lower()
        if attr not in normalized:
            attributes.append((name, name, '"', " ", "=", None))
            normalized[attr] = len(attributes) - 1

    return attributes


class RepeatItem:
    __slots__ = "length", "_iterator"

    __allow_access_to_unprotected_subobjects__ = True

    def __init__(self, iterator, length):
        self.length = length
        self._iterator = iterator

    def __iter__(self):
        return self._iterator

    try:
        iter(()).__len__
    except AttributeError:
        @descriptorint
        def index(self):
            try:
                remaining = self._iterator.__length_hint__()
            except AttributeError:
                remaining = len(tuple(copy.copy(self._iterator)))
            return self.length - remaining - 1
    else:
        @descriptorint
        def index(self):
            remaining = self._iterator.__len__()
            return self.length - remaining - 1

    @descriptorint
    def start(self):
        return self.index == 0

    @descriptorint
    def end(self):
        return self.index == self.length - 1

    @descriptorint
    def number(self):
        return self.index + 1

    @descriptorstr
    def odd(self):
        """Returns a true value if the item index is odd.

        >>> it = RepeatItem(iter(("apple", "pear")), 2)

        >>> next(it._iterator)
        'apple'
        >>> it.odd()
        ''

        >>> next(it._iterator)
        'pear'
        >>> it.odd()
        'odd'
        """

        return self.index % 2 == 1 and 'odd' or ''

    @descriptorstr
    def even(self):
        """Returns a true value if the item index is even.

        >>> it = RepeatItem(iter(("apple", "pear")), 2)

        >>> next(it._iterator)
        'apple'
        >>> it.even()
        'even'

        >>> next(it._iterator)
        'pear'
        >>> it.even()
        ''
        """

        return self.index % 2 == 0 and 'even' or ''

    @descriptorstr
    def parity(self):
        """Return 'odd' or 'even' depending on the position's parity

        Useful for assigning CSS class names to table rows.
        """

        return self.index % 2 == 0 and 'even' or 'odd'

    def next(self):
        raise NotImplementedError(
            "Method not implemented (can't update local variable).")

    def _letter(self, base=ord('a'), radix=26):
        """Get the iterator position as a lower-case letter

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.letter()
        'a'
        >>> next(it._iterator)
        'pear'
        >>> it.letter()
        'b'
        >>> next(it._iterator)
        'orange'
        >>> it.letter()
        'c'
        """

        index = self.index
        if index < 0:
            raise TypeError("No iteration position")
        s = ""
        while True:
            index, off = divmod(index, radix)
            s = chr(base + off) + s
            if not index:
                return s

    letter = descriptorstr(_letter)

    @descriptorstr
    def Letter(self):
        """Get the iterator position as an upper-case letter

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.Letter()
        'A'
        >>> next(it._iterator)
        'pear'
        >>> it.Letter()
        'B'
        >>> next(it._iterator)
        'orange'
        >>> it.Letter()
        'C'
        """

        return self._letter(base=ord('A'))

    @descriptorstr
    def Roman(self, rnvalues=(
        (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
            (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'))):
        """Get the iterator position as an upper-case roman numeral

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.Roman()
        'I'
        >>> next(it._iterator)
        'pear'
        >>> it.Roman()
        'II'
        >>> next(it._iterator)
        'orange'
        >>> it.Roman()
        'III'
        """

        n = self.index + 1
        s = ""
        for v, r in rnvalues:
            rct, n = divmod(n, v)
            s = s + r * rct
        return s

    @descriptorstr
    def roman(self):
        """Get the iterator position as a lower-case roman numeral

        >>> it = RepeatItem(iter(("apple", "pear", "orange")), 3)
        >>> next(it._iterator)
        'apple'
        >>> it.roman()
        'i'
        >>> next(it._iterator)
        'pear'
        >>> it.roman()
        'ii'
        >>> next(it._iterator)
        'orange'
        >>> it.roman()
        'iii'
        """

        return self.Roman().lower()


if interfaces is not None:
    zope.interface.classImplements(RepeatItem, interfaces.ITALESIterator)


class RepeatDict:
    """Repeat dictionary implementation.

    >>> repeat = RepeatDict({})
    >>> iterator, length = repeat('numbers', range(5))
    >>> length
    5

    >>> repeat['numbers']
    <chameleon.tal.RepeatItem object at ...>

    >>> repeat.numbers
    <chameleon.tal.RepeatItem object at ...>

    >>> getattr(repeat, 'missing_key', None) is None
    True

    >>> try:
    ...     from chameleon import interfaces
    ...     interfaces.ITALESIterator(repeat,None) is None
    ... except ImportError:
    ...     True
    ...
    True
    """

    __slots__ = "__setitem__", "__getitem__"

    def __init__(self, d):
        self.__setitem__ = d.__setitem__
        self.__getitem__ = d.__getitem__

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __call__(self, key, iterable):
        """We coerce the iterable to a tuple and return an iterator
        after registering it in the repeat dictionary."""

        iterable = list(iterable) if iterable is not None else ()

        length = len(iterable)
        iterator = iter(iterable)

        # Insert as repeat item
        self[key] = RepeatItem(iterator, length)

        return iterator, length


class ErrorInfo:
    """Information about an exception passed to an on-error handler."""

    def __init__(self, err, position=(None, None)):
        if isinstance(err, Exception):
            self.type = err.__class__
            self.value = err
        else:
            self.type = err
            self.value = None
        self.lineno = position[0]
        self.offset = position[1]


if interfaces is not None:
    zope.interface.classImplements(
        ErrorInfo, interfaces.ITALExpressionErrorInfo)
