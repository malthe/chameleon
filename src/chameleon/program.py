try:
    str = unicode
except NameError:
    long = int

from .exc import ParseError
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

    restricted_namespace = True

    def __init__(self, source, mode="xml", filename=None, tokenizer=None):
        if tokenizer is None:
            tokenizer = self.tokenizers[mode]
        tokens = tokenizer(source, filename)
        parser = ElementParser(tokens, self.DEFAULT_NAMESPACES, self.restricted_namespace)

        self.body = []

        for kind, args in parser:
            node = self.visit(kind, args)
            if node is not None:
                self.body.append(node)

        if parser.index:
            # The ``index`` attribute contains a sequence of open HTML tags
            # which get consumed as their closing tags are found. If the
            # sequence contains any values after parsing then the template has
            # unclosed tags.
            name, pos = parser.index.pop()
            raise ParseError('No closing tag.', name)

    def visit(self, kind, args):
        visitor = getattr(self, "visit_%s" % kind)
        return visitor(*args)
