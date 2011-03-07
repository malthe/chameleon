from .astutil import Node


class UseExternalMacro(Node):
    """Extend external macro."""

    _fields = "expression", "slots", "extend"


class Sequence(Node):
    """Element sequence."""

    _fields = "items",


class Content(Node):
    """Content substitution.

    If ``msgid`` is non-trivial, the content will be subject to
    translation. The provided ``default`` is the default content.
    """

    _fields = "expression", "msgid", "escape"


class Expression(Node):
    """String expression for evaluation by expression engine."""

    _fields = "value",

    def __repr__(self):
        try:
            line, column = self.value.location
        except AttributeError:
            line, column = 0, 0

        return "<Expression %r (%d:%d)>" % (self.value, line, column)


class Negate(Node):
    """Wraps an expression with a negation."""

    _fields = "value",


class Element(Node):
    """XML element."""

    _fields = "start", "end", "content"


class Attribute(Node):
    """Element attribute."""

    _fields = "name", "expression", "quote", "eq", "space", "escape"


class Start(Node):
    """Start-tag."""

    _fields = "name", "prefix", "suffix", "attributes"


class End(Node):
    """End-tag."""

    _fields = "name", "space", "prefix", "suffix"


class Condition(Node):
    """Node visited only if some condition holds."""

    _fields = "expression", "node", "orelse"


class Identity(Node):
    """Condition expression that is true on identity."""

    _fields = "expression", "value"


class Equality(Node):
    """Condition expression that is true on equality."""

    _fields = "expression", "value"


class Marker(Node):
    """Represents a marker object.

    The ``name`` string must be unique across the template program.
    """

    _fields = "name",


class Cache(Node):
    """Cache (evaluate only once) the value of ``expression`` inside
    ``node``.
    """

    _fields = "expressions", "node"


class Assignment(Node):
    """Variable assignment."""

    _fields = "names", "expression", "local"


class Define(Node):
    """Variable definition in scope."""

    _fields = "assignments", "node"


class Repeat(Assignment):
    """Iterate over provided assignment and repeat body."""

    _fields = "names", "expression", "local", "whitespace", "node"


class Macro(Node):
    """Macro definition."""

    _fields = "name", "body"


class Program(Node):
    _fields = "name", "body"


class Text(Node):
    """Static text output."""

    _fields = "value",


class Interpolation(Text):
    """String interpolation output."""

    _fields = "value", "escape"


class Translate(Node):
    """Translate node."""

    _fields = "msgid", "node"


class Name(Node):
    """Translation name."""

    _fields = "name", "node"


class Domain(Node):
    """Update translation domain."""

    _fields = "name", "node"


class OnError(Node):
    _fields = "fallback", "node"


class UseInternalMacro(Node):
    """Use internal macro (defined inside same program)."""

    _fields = "name",


class FillSlot(Node):
    """Fill a macro slot."""

    _fields = "name", "node"


class DefineSlot(Node):
    """Define a macro slot."""

    _fields = "name", "node"
