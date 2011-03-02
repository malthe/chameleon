import traceback

from .tokenize import Token
from .utils import format_kwargs


class TemplateError(Exception):
    def __init__(self, msg, token):
        if not isinstance(token, Token):
            token = Token(token, 0)

        self.msg = msg
        self.token = token
        self.filename = token.filename

    def __str__(self):
        text = "%s\n\n" % self.msg
        text += "   - String:   \"%s\"" % self.token

        if self.filename:
            text += "\n"
            text += "   - Filename: %s" % self.filename

        try:
            line, column = self.token.location
        except AttributeError:
            pass
        else:
            text += "\n"
            text += "   - Location: (%d:%d)" % (line, column)

        return text

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


class RenderError(TemplateError):
    """An error occurred during rendering."""

    def __init__(self, errors, econtext, rcontext):
        kwargs = rcontext.copy()
        kwargs.update(econtext)

        self._errors = errors
        self._kwargs = kwargs

    def __str__(self):
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

        out = ["An uncaught exception was raised.", ""]

        for error in self.flatten():
            expression, line, column, filename, exc = error
            out += traceback.format_exception_only(type(exc), exc)
            out.append(" - Expression: \"%s\"" % expression)
            out.append(" - Filename:   %s" % (filename or "<string>"))
            out.append(" - Location:   (%d:%d)" % (line, column))

        out.append(" - Arguments:  %s" % "\n".join(formatted))

        return "\n".join(out)

    def flatten(self):
        for error in self._errors:
            exc = error[-1]
            if isinstance(exc, RenderError):
                for error in exc.flatten():
                    yield error
            else:
                yield error
