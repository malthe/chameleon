# -*- coding: utf-8 -*-

import traceback

from .utils import format_kwargs
from .utils import safe_native
from .tokenize import Token
from .config import SOURCE_EXPRESSION_MARKER_LENGTH as LENGTH


def compute_source_marker(line, column, expression, size):
    """Computes source marker location string.

    >>> def test(l, c, e, s):
    ...     s, marker = compute_source_marker(l, c, e, s)
    ...     out = s + '\\n' + marker
    ...
    ...     # Replace dot with middle-dot to work around doctest ellipsis
    ...     print(out.replace('...', '···'))

    >>> test('foo bar', 4, 'bar', 7)
    foo bar
        ^^^

    >>> test('foo ${bar}', 4, 'bar', 10)
    foo ${bar}
          ^^^

    >>> test('  foo bar', 6, 'bar', 6)
    ··· oo bar
           ^^^

    >>> test('  foo bar baz  ', 6, 'bar', 6)
    ··· o bar ···
          ^^^

    The entire expression is always shown, even if ``size`` does not
    accomodate for it.

    >>> test('  foo bar baz  ', 6, 'bar baz', 10)
    ··· oo bar baz
           ^^^^^^^

    >>> test('      foo bar', 10, 'bar', 5)
    ··· o bar
          ^^^

    >>> test('      foo bar', 10, 'boo', 5)
    ··· o bar
          ^

    """

    s = line.lstrip()
    column -= len(line) - len(s)
    s = s.rstrip()

    try:
        i  = s[column:].index(expression)
    except ValueError:
        # If we can't find the expression
        # (this shouldn't happen), simply
        # use a standard size marker
        marker = "^"
    else:
        column += i
        marker = "^" * len(expression)

    if len(expression) > size:
        offset = column
        size = len(expression)
    else:
        window = (size - len(expression)) / 2.0
        offset = column - window
        offset -= min(3, max(0, column + window + len(expression) - len(s)))
        offset = int(offset)

    if offset > 0:
        s = s[offset:]
        r = s.lstrip()
        d = len(s) - len(r)
        s = "... " + r
        column += 4 - d
        column -= offset

        # This also adds to the displayed length
        size += 4

    if len(s) > size:
        s = s[:size].rstrip() + " ..."

    return s, column * " " + marker


def ellipsify(string, limit):
    if len(string) > limit:
        return "... " + string[-(limit - 4):]

    return string


class RenderError(Exception):
    """An error raised during rendering.

    This class is used as a mixin which is added to the original
    exception.
    """


class TemplateError(Exception):
    """An error raised by Chameleon.

    >>> from chameleon.tokenize import Token
    >>> token = Token('token')
    >>> message = 'message'

    Make sure the exceptions can be copied:

    >>> from copy import copy
    >>> copy(TemplateError(message, token))
    TemplateError('message', 'token')

    And pickle/unpickled:

    >>> from pickle import dumps, loads
    >>> loads(dumps(TemplateError(message, token), -1))
    TemplateError('message', 'token')

    """

    def __init__(self, msg, token):
        if not isinstance(token, Token):
            token = Token(token, 0)

        Exception.__init__(self, msg, token)

    def __copy__(self):
        inst = Exception.__new__(type(self))
        inst.args = self.args
        return inst

    def __str__(self):
        text = "%s\n\n" % self.args[0]
        text += " - String:     \"%s\"" % safe_native(self.token)

        if self.filename:
            text += "\n"
            text += " - Filename:   %s" % self.filename

        line, column = self.location
        text += "\n"
        text += " - Location:   (line %d: col %d)" % (line, column)

        return text

    def __repr__(self):
        try:
            return "%s('%s', '%s')" % (
                self.__class__.__name__, self.args[0], safe_native(self.token)
                )
        except AttributeError:
            return object.__repr__(self)

    @property
    def token(self):
        return self.args[1]

    @property
    def filename(self):
        return self.token.filename

    @property
    def location(self):
        return self.token.location

    @property
    def offset(self):
        return getattr(self.token, "pos", 0)


class ParseError(TemplateError):
    """An error occurred during parsing.

    Indicates an error on the structural level.
    """


class CompilationError(TemplateError):
    """An error occurred during compilation.

    Indicates a general compilation error.
    """


class TranslationError(TemplateError):
    """An error occurred during translation.

    Indicates a general translation error.
    """


class LanguageError(CompilationError):
    """Language syntax error.

    Indicates a syntactical error due to incorrect usage of the
    template language.
    """


class ExpressionError(LanguageError):
    """An error occurred compiling an expression.

    Indicates a syntactical error in an expression.
    """


class ExceptionFormatter(object):
    def __init__(self, errors, econtext, rcontext):
        kwargs = rcontext.copy()
        kwargs.update(econtext)

        for name in tuple(kwargs):
            if name.startswith('__'):
                del kwargs[name]

        self._errors = errors
        self._kwargs = kwargs

    def __call__(self):
        # Format keyword arguments; consecutive arguments are indented
        # for readability
        try:
            formatted = format_kwargs(self._kwargs)
        except:
            # the ``pprint.pformat`` method calls the representation
            # method of the arguments; this may fail and since we're
            # already in an exception handler, there's no point in
            # pursuing this further
            formatted = ()

        for index, string in enumerate(formatted[1:]):
            formatted[index + 1] = " " * 15 + string

        out = []
        seen = set()

        for error in reversed(self._errors):
            expression, line, column, filename, exc = error

            if exc in seen:
                continue

            seen.add(exc)

            if isinstance(exc, UnicodeDecodeError):
                string = safe_native(exc.object)

                s, marker = compute_source_marker(
                    string, exc.start, string[exc.start:exc.end], LENGTH
                    )

                out.append(" - Stream:     %s" % s)
                out.append("               %s" % marker)

            _filename = ellipsify(filename, 60) if filename else "<string>"

            out.append(" - Expression: \"%s\"" % expression)
            out.append(" - Filename:   %s" % _filename)
            out.append(" - Location:   (line %d: col %d)" % (line, column))

            if filename and line and column:
                try:
                    f = open(filename, 'r')
                except IOError:
                    pass
                else:
                    try:
                        # Pick out source line and format marker
                        for i, l in enumerate(f):
                            if i + 1 == line:
                                s, marker = compute_source_marker(
                                    l, column, expression, LENGTH
                                    )

                                out.append(" - Source:     %s" % s)
                                out.append("               %s" % marker)
                                break
                    finally:
                        f.close()

        out.append(" - Arguments:  %s" % "\n".join(formatted))

        formatted = traceback.format_exception_only(type(exc), exc)[-1]
        formatted_class = "%s:" % type(exc).__name__

        if formatted.startswith(formatted_class):
            formatted = formatted[len(formatted_class):].lstrip()

        return "\n".join(map(safe_native, [formatted] + out))
