from __future__ import annotations

import traceback
from typing import TYPE_CHECKING
from typing import Any

from chameleon.config import SOURCE_EXPRESSION_MARKER_LENGTH as LENGTH
from chameleon.tokenize import Token
from chameleon.utils import create_formatted_exception
from chameleon.utils import safe_native


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from typing_extensions import Self


def compute_source_marker(
    line: str,
    column: int,
    expression: str,
    size: int
) -> tuple[str, str]:
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
    accommodate for it.

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
        i = s[column:].index(expression)
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
        f_offset = column - window
        f_offset -= min(3, max(0, column + window + len(expression) - len(s)))
        offset = int(f_offset)

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


def iter_source_marker_lines(
    source: Iterable[str],
    expression: str,
    line: int,
    column: int
) -> Iterator[str]:

    for i, l in enumerate(source):
        if i + 1 != line:
            continue

        s, marker = compute_source_marker(
            l, column, expression, LENGTH
        )

        yield " - Source:     %s" % s
        yield "               %s" % marker
        break


def ellipsify(string: str, limit: int) -> str:
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

    args: tuple[str, Token]

    def __init__(self, msg: str, token: Token) -> None:
        if not isinstance(token, Token):
            token = Token(token, 0)

        Exception.__init__(self, msg, token)

    def __copy__(self) -> Self:
        inst = Exception.__new__(type(self))
        inst.args = self.args
        return inst

    def __str__(self) -> str:
        text = "%s\n\n" % self.args[0]
        text += " - String:     \"%s\"" % safe_native(self.token)

        if self.filename:
            text += "\n"
            text += " - Filename:   %s" % self.filename

        lineno, column = self.location
        text += "\n"
        text += " - Location:   (line %d: col %d)" % (lineno, column)

        lines: Iterable[str]
        if lineno and column:
            if self.token.source:
                lines = iter_source_marker_lines(
                    self.token.source.splitlines(),
                    self.token, lineno, column
                )
            elif self.filename and not self.filename.startswith('<'):
                try:
                    f = open(self.filename)
                except OSError:
                    pass
                else:
                    lines = iter_source_marker_lines(
                        iter(f), self.token, lineno, column
                    )
                    try:
                        lines = list(lines)
                    finally:
                        f.close()
            else:
                lines = ()

            # Prepend newlines.
            for line in lines:
                text += "\n" + safe_native(line)

        return text

    def __repr__(self) -> str:
        try:
            return "{}('{}', '{}')".format(
                self.__class__.__name__, self.args[0], safe_native(self.token)
            )
        except AttributeError:
            return object.__repr__(self)

    @property
    def token(self) -> Token:
        return self.args[1]

    @property
    def filename(self) -> str:
        return self.token.filename

    @property
    def location(self) -> tuple[int, int]:
        return self.token.location

    @property
    def offset(self) -> int:
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


class ExceptionFormatter:
    def __init__(
        self,
        errors: list[tuple[str, int, int, str, BaseException]],
        econtext: Mapping[str, object],
        rcontext: dict[str, Any],
        value_repr: Callable[[object], str]
    ) -> None:

        kwargs = rcontext.copy()
        kwargs.update(econtext)

        for name in tuple(kwargs):
            if name.startswith('__'):
                del kwargs[name]

        self._errors = errors
        self._kwargs = kwargs
        self._value_repr = value_repr

    def __call__(self) -> str:
        # Format keyword arguments; consecutive arguments are indented
        # for readability
        formatted_args = [
            "{}: {}".format(name, self._value_repr(value))
            for name, value in self._kwargs.items()
        ]

        for index, string in enumerate(formatted_args[1:]):
            formatted_args[index + 1] = " " * 15 + string

        out = []

        for error in self._errors:
            expression, line, column, filename, exc = error

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

            if filename and not filename.startswith('<') and line and column:
                try:
                    f = open(filename)
                except OSError:
                    pass
                else:
                    lines = iter_source_marker_lines(
                        iter(f), expression, line, column
                    )
                    try:
                        out.extend(lines)
                    finally:
                        f.close()

        out.append(" - Arguments:  %s" % "\n".join(formatted_args))

        if isinstance(exc.__str__, ExceptionFormatter):
            # This is a nested error that has already been wrapped
            # We must unwrap it before trying to format it to prevent
            # recursion
            exc = create_formatted_exception(
                exc, type(exc), exc._original__str__)  # type: ignore
        formatted = traceback.format_exception_only(type(exc), exc)[-1]
        formatted_class = "%s:" % type(exc).__name__

        if formatted.startswith(formatted_class):
            formatted = formatted[len(formatted_class):].lstrip()

        return "\n".join(map(safe_native, [formatted] + out))
