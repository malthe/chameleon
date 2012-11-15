import re
import logging

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from .exc import ParseError
from .namespaces import XML_NS
from .tokenize import Token

match_tag_prefix_and_name = re.compile(
    r'^(?P<prefix></?)(?P<name>([^:\n ]+:)?[^ \n\t>/]+)'
    '(?P<suffix>(?P<space>\s*)/?>)?',
    re.UNICODE | re.DOTALL)
match_single_attribute = re.compile(
    r'(?P<space>\s+)(?!\d)'
    r'(?P<name>[^ =/>\n\t]+)'
    r'((?P<eq>\s*=\s*)'
    r'((?P<quote>[\'"])(?P<value>.*?)(?P=quote)|'
    r'(?P<alt_value>[^\s\'">/]+))|'
    r'(?P<simple_value>(?![ \\n\\t\\r]*=)))',
    re.UNICODE | re.DOTALL)
match_comment = re.compile(
    r'^<!--(?P<text>.*)-->$', re.DOTALL)
match_cdata = re.compile(
    r'^<!\[CDATA\[(?P<text>.*)\]>$', re.DOTALL)
match_declaration = re.compile(
    r'^<!(?P<text>[^>]+)>$', re.DOTALL)
match_processing_instruction = re.compile(
    r'^<\?(?P<name>\w+)(?P<text>.*?)\?>', re.DOTALL)
match_xml_declaration = re.compile(r'^<\?xml(?=[ /])', re.DOTALL)

log = logging.getLogger('chameleon.parser')


def substitute(regex, repl, token):
    if not isinstance(token, Token):
        token = Token(token)

    return Token(
        regex.sub(repl, token),
        token.pos,
        token.source,
        token.filename
        )


def groups(m, token):
    result = []
    for i, group in enumerate(m.groups()):
        if group is not None:
            j, k = m.span(i + 1)
            group = token[j:k]

        result.append(group)

    return tuple(result)


def groupdict(m, token):
    d = m.groupdict()
    for name, value in d.items():
        if value is not None:
            i, j = m.span(name)
            d[name] = token[i:j]

    return d


def match_tag(token, regex=match_tag_prefix_and_name):
    m = regex.match(token)
    d = groupdict(m, token)

    end = m.end()
    token = token[end:]

    attrs = d['attrs'] = []
    for m in match_single_attribute.finditer(token):
        attr = groupdict(m, token)
        alt_value = attr.pop('alt_value', None)
        if alt_value is not None:
            attr['value'] = alt_value
            attr['quote'] = ''
        simple_value = attr.pop('simple_value', None)
        if simple_value is not None:
            attr['quote'] = ''
            attr['value'] = ''
            attr['eq'] = ''
        attrs.append(attr)
        d['suffix'] = token[m.end():]

    return d


def parse_tag(token, namespace):
    node = match_tag(token)

    update_namespace(node['attrs'], namespace)

    if ':' in node['name']:
        prefix = node['name'].split(':')[0]
    else:
        prefix = None

    default = node['namespace'] = namespace.get(prefix, XML_NS)

    node['ns_attrs'] = unpack_attributes(
        node['attrs'], namespace, default)

    return node


def update_namespace(attributes, namespace):
    # possibly update namespaces; we do this in a separate step
    # because this assignment is irrespective of order
    for attribute in attributes:
        name = attribute['name']
        value = attribute['value']
        if name == 'xmlns':
            namespace[None] = value
        elif name.startswith('xmlns:'):
            namespace[name[6:]] = value


def unpack_attributes(attributes, namespace, default):
    namespaced = OrderedDict()

    for index, attribute in enumerate(attributes):
        name = attribute['name']
        value = attribute['value']

        if ':' in name:
            prefix = name.split(':')[0]
            name = name[len(prefix) + 1:]
            try:
                ns = namespace[prefix]
            except KeyError:
                raise KeyError(
                    "Undefined namespace prefix: %s." % prefix)
        else:
            ns = default
        namespaced[ns, name] = value

    return namespaced


def identify(string):
    if string.startswith("<"):
        if string.startswith("<!--"):
            return "comment"
        if string.startswith("<![CDATA["):
            return "cdata"
        if string.startswith("<!"):
            return "declaration"
        if string.startswith("<?xml"):
            return "xml_declaration"
        if string.startswith("<?"):
            return "processing_instruction"
        if string.startswith("</"):
            return "end_tag"
        if string.endswith("/>"):
            return "empty_tag"
        if string.endswith(">"):
            return "start_tag"
        return "error"
    return "text"


class ElementParser(object):
    """Parses tokens into elements."""

    def __init__(self, stream, default_namespaces):
        self.stream = stream
        self.queue = []
        self.index = []
        self.namespaces = [default_namespaces.copy()]

    def __iter__(self):
        for token in self.stream:
            item = self.parse(token)
            self.queue.append(item)

        return iter(self.queue)

    def parse(self, token):
        kind = identify(token)
        visitor = getattr(self, "visit_%s" % kind, self.visit_default)
        return visitor(kind, token)

    def visit_comment(self, kind, token):
        return "comment", (token, )

    def visit_cdata(self, kind, token):
        return "cdata", (token, )

    def visit_default(self, kind, token):
        return "default", (token, )

    def visit_processing_instruction(self, kind, token):
        m = match_processing_instruction.match(token)
        if m is None:
            return self.visit_default(kind, token)

        return "processing_instruction", (groupdict(m, token), )

    def visit_text(self, kind, token):
        return kind, (token, )

    def visit_start_tag(self, kind, token):
        namespace = self.namespaces[-1].copy()
        self.namespaces.append(namespace)
        node = parse_tag(token, namespace)
        self.index.append((node['name'], len(self.queue)))
        return kind, (node, )

    def visit_end_tag(self, kind, token):
        try:
            namespace = self.namespaces.pop()
        except IndexError:
            raise ParseError("Unexpected end tag.", token)

        node = parse_tag(token, namespace)

        while self.index:
            name, pos = self.index.pop()
            if name == node['name']:
                start, = self.queue.pop(pos)[1]
                children = self.queue[pos:]
                del self.queue[pos:]
                break
        else:
            raise ParseError("Unexpected end tag.", token)

        return "element", (start, node, children)

    def visit_empty_tag(self, kind, token):
        namespace = self.namespaces[-1].copy()
        node = parse_tag(token, namespace)
        return "element", (node, None, [])
