try:
    str = unicode
except NameError:
    long = int

from .tokenize import iter_xml
from .tokenize import iter_text
from .parser import ElementParser
from .namespaces import XML_NS
from .namespaces import XMLNS_NS


class ElementProgram(object):
    DEFAULT_NAMESPACES = {
        'xmlns': XMLNS_NS,
        'xml': XML_NS,
        }

    tokenizers = {
        'xml': iter_xml,
        'text': iter_text,
        }

    def __init__(self, source, mode="xml", filename=None):
        tokenizer = self.tokenizers[mode]
        tokens = tokenizer(source, filename)
        parser = ElementParser(tokens, self.DEFAULT_NAMESPACES)

        self.body = []

        for kind, args in parser:
            node = self.visit(kind, args)
            if node is not None:
                self.body.append(node)

    def visit(self, kind, args):
        visitor = getattr(self, "visit_%s" % kind)
        return visitor(*args)
