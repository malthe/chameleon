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

import re

from .exc import CompilationError
from .utils import unicode_string

NAME_RE = r"[a-zA-Z][-a-zA-Z0-9_]*"

WHITELIST = frozenset([
    "translate",
    "domain",
    "target",
    "source",
    "attributes",
    "data",
    "name",
    "mode",
    "xmlns",
    "xml"
    ])

_interp_regex = re.compile(r'(?<!\$)(\$(?:(%(n)s)|{(%(n)s)}))'
    % ({'n': NAME_RE}))


try:  # pragma: no cover
    str = unicode
except NameError:
    pass

try:  # pragma: no cover
    # optional: `zope.i18n`, `zope.i18nmessageid`
    from zope.i18n import interpolate
    from zope.i18n import translate
    from zope.i18nmessageid import Message
except ImportError:   # pragma: no cover

    def fast_translate(msgid, domain=None, mapping=None, context=None,
                       target_language=None, default=None):
        if default is None:
            return msgid

        if mapping:
            def replace(match):
                whole, param1, param2 = match.groups()
                return unicode_string(mapping.get(param1 or param2, whole))
            return _interp_regex.sub(replace, default)

        return default
else:   # pragma: no cover
    def fast_translate(msgid, domain=None, mapping=None, context=None,
                       target_language=None, default=None):
        if msgid is None:
            return

        if target_language is not None:
            result = translate(
                msgid, domain=domain, mapping=mapping, context=context,
                target_language=target_language, default=default)
            if result != msgid:
                return result

        if isinstance(msgid, Message):
            default = msgid.default
            mapping = msgid.mapping

        if default is None:
            default = str(msgid)

        if not isinstance(default, basestring):
            return default

        return interpolate(default, mapping)


def parse_attributes(attrs, xml=True):
    d = {}

    # filter out empty items, eg:
    # i18n:attributes="value msgid; name msgid2;"
    # would result in 3 items where the last one is empty
    attrs = [spec for spec in attrs.split(";") if spec]

    for spec in attrs:
        if ',' in spec:
            raise CompilationError(
                "Attribute must not contain comma. Use semicolon to "
                "list multiple attributes", spec
                )
        parts = spec.split()
        if len(parts) == 2:
            attr, msgid = parts
        elif len(parts) == 1:
            attr = parts[0]
            msgid = None
        else:
            raise CompilationError(
                "Illegal i18n:attributes specification.", spec)
        if not xml:
            attr = attr.lower()
        attr = attr.strip()
        if attr in d:
            raise CompilationError(
                "Attribute may only be specified once in i18n:attributes", attr)
        d[attr] = msgid

    return d
