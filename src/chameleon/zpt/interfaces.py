try:
    from zope.interface import Interface
except ImportError:
    class Interface(object):
        pass

class IExpressionTranslator(Interface):
    """This interface defines an expression translation utility or
    adapter; most implementations will subclass
    ``chameleon.zpt.language.TALES`` and override one or more
    methods."""

    def validate(string):
        """Void method which raises a syntax error if ``string`` is
        not a valid expression."""

    def translate(string):
        """Translates ``string`` into an expression type (see
        ``chameleon.core.types``)."""

    def tales(string):
        """TALES Expression.

        Specification:

            tales ::= (pragma:) expression ['|' tales]

        """

    def declaration(string):
        """A variable definition.

        Specification:

           variables ::= variable_name [',' variables]

        This corresponds to Python variable assignment which supports
        assignment in tuples.
        """

    def mapping(string):
        """A mapping definition.

        Specification:

            mapping ::= token value [';' mapping]

        """

    def definition(string):
        """Variable Assignment.

        Specification:

           definition ::= declaration expression

        """

    def definitions(string):
        """Multiple variable definitions.

        Specification:

           definitions ::= definition [';' definitions]

        """
