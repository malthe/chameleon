try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

try:
    str = unicode
except NameError:
    long = int

from .tokenize import iter_xml
from .parser import ElementParser
from .namespaces import XML_NS
from .namespaces import XMLNS_NS


class ElementProgram(object):
    DEFAULT_NAMESPACES = {
        'xmlns': XMLNS_NS,
        'xml': XML_NS,
        }

    def __init__(self, source, filename=None):
        tokens = iter_xml(source, filename)
        parser = ElementParser(tokens, self.DEFAULT_NAMESPACES)

        self.body = []

        for kind, args in parser:
            node = self.visit(kind, args)
            if node is not None:
                self.body.append(node)

    def visit(self, kind, args):
        visitor = getattr(self, "visit_%s" % kind)
        return visitor(*args)
