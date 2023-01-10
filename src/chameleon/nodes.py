from .astutil import Node


class UseExternalMacro(Node):
    """Extend external macro."""

    _fields = "expression", "slots", "extend"


class Sequence(Node):
    """Element sequence."""

    _fields = "items",

    def __nonzero__(self):
        return bool(self.items)


class Content(Node):
    """Content substitution."""

    _fields = "expression", "char_escape", "translate"


class CodeBlock(Node):
    _fields = "source",


class Value(Node):
    """Expression object value."""

    _fields = "value", "default", "default_marker"

    default = None

    default_marker = None

    def __repr__(self):
        try:
            line, column = self.value.location
        except AttributeError:
            line, column = 0, 0

        return "<%s %r (%d:%d)>" % (
            type(self).__name__, self.value, line, column
        )


class Substitution(Value):
    """Expression value for text substitution."""

    _fields = "value", "char_escape", "default", "default_marker"

    default = None


class Boolean(Value):
    _fields = "value", "s", "default", "default_marker"


class Negate(Node):
    """Wraps an expression with a negation."""

    _fields = "value",


class Element(Node):
    """XML element."""

    _fields = "start", "end", "content"


class DictAttributes(Node):
    """Element attributes from one or more Python dicts."""

    _fields = "expression", "char_escape", "quote", "exclude"


class Attribute(Node):
    """Element attribute."""

    _fields = (
        "name", "expression", "quote", "eq", "space", "default", "filters")


class Start(Node):
    """Start-tag."""

    _fields = "name", "prefix", "suffix", "attributes"


class End(Node):
    """End-tag."""

    _fields = "name", "space", "prefix", "suffix"


class Condition(Node):
    """Node visited only if one of the condition holds."""

    _fields = "expression", "node", "orelse"


class Op(Node):
    """An operator node."""


class Is(Op):
    """Object identity."""


class IsNot(Op):
    """Object identity."""


class Equals(Op):
    """Object equality."""


class Logical(Node):
    """Logical operator."""

    _fields = "expressions",


class And(Logical):
    """All terms must be met."""


class Or(Logical):
    """At least one term must be met."""


class BinOp(Node):
    """Binary comparison."""

    _fields = "left", "op", "right"


class Cache(Node):
    """Cache (evaluate only once) the value of ``expression`` inside
    ``node``.
    """

    _fields = "expressions", "node"


class Cancel(Cache):
    _fields = "expressions", "node", "value"


class Copy(Node):
    _fields = "expression",


class Assignment(Node):
    """Variable assignment."""

    _fields = "names", "expression", "local"


class Alias(Assignment):
    """Alias assignment.

    Note that ``expression`` should be a cached or global value.
    """

    local = False


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


class Module(Node):
    _fields = "name", "program",


class Context(Node):
    _fields = "node",


class Text(Node):
    """Static text output."""

    _fields = "value",


class Interpolation(Node):
    """String interpolation output."""

    _fields = (
        "value", "braces_required", "translation", "default", "default_marker")


class Translate(Node):
    """Translate node."""

    _fields = "msgid", "node"


class Name(Node):
    """Translation name."""

    _fields = "name", "node"


class Domain(Node):
    """Update translation domain."""

    _fields = "name", "node"


class TxContext(Node):
    """Update translation context."""

    _fields = "name", "node"


class OnError(Node):
    _fields = "fallback", "name", "node"


class UseInternalMacro(Node):
    """Use internal macro (defined inside same program)."""

    _fields = "name",


class FillSlot(Node):
    """Fill a macro slot."""

    _fields = "name", "node"


class DefineSlot(Node):
    """Define a macro slot."""

    _fields = "name", "node"
