from .tokenize import Token


class TemplateError(Exception):
    def __init__(self, msg, token):
        if not isinstance(token, Token):
            token = Token(token, 0)

        self.msg = msg
        self.token = token
        self.filename = token.filename

    def __str__(self):
        try:
            line, column = self.token.location
        except AttributeError:
            line, column = -1, -1

        text = "%s: '%s' [%d:%d]" % (self.msg, self.token, line, column)

        if self.filename:
            text = "%s.\n\n%s" % (self.filename, text)

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


