import translation
import template
import generation
import doctypes
import etree
import config
import utils
import types
import filecache

from StringIO import StringIO

def pyexp(*exps):
    if len(exps) == 1:
        return types.value(exps[0])
    return types.parts([types.value(exp) for exp in exps])

def setup_stream(encoding=None):
    class symbols(translation.Node.symbols):
        out = '_out'
        write = '_write'

    out = StringIO()
    write = out.write
    stream = generation.CodeIO(symbols, encoding=encoding)
    stream.scope.append(set())
    return out, write, stream

def render_xhtml(body, **kwargs):
    func = compile_template(mock_parser, mock_parser.parse, body)
    return func(**kwargs)    
    
def render_text(body, **kwargs):
    func = compile_template(mock_parser, mock_parser.parse_text, body)
    return func(**kwargs)    

def compile_xhtml(body):
    return compile_template(mock_parser, mock_parser.parse, body)

def compile_template(parser, parse_method, body, encoding=None,
                     macro=None, global_scope=True, explicit_doctype=None, **kwargs):
    tree = parse_method(body)
    if '<?xml ' in body:
        xml_declaration = \
            """<?xml version="%s" encoding="%s" standalone="no" ?>""" % (
            tree.docinfo.xml_version, tree.docinfo.encoding)
    else:
        xml_declaration = None

    if not explicit_doctype is doctypes.no_doctype and not explicit_doctype:
        explicit_doctype = parser.doctype
    compiler = translation.Compiler(
        tree, xml_declaration=xml_declaration,
        encoding=encoding, explicit_doctype=explicit_doctype)

    source = compiler(macro, global_scope)
    registry = filecache.TemplateRegistry()
    registry.add(None, source)
    func = registry[None]
    def render(target_language=None, **kwargs):
        kwargs.setdefault("_slots", utils.emptydict)
        rcontext = utils.econtext(kwargs)
        econtext = rcontext.copy()
        return func(econtext, rcontext)
    return render

class MockElement(translation.Element):
    class Node(translation.Node):
        ns_omit = (
            "http://xml.zope.org/namespaces/meta",
            "http://www.w3.org/2001/XInclude")
        
        def __getattr__(self, name):
            return None

        @property
        def omit(self):
            if self.element.meta_omit is not None:
                return self.element.meta_omit or True
            if self.content:
                return True
            if self.include:
                return True

        @property
        def content(self):
            return self.element.meta_replace
        
        @property
        def cdata(self):
            return self.element.meta_cdata

        @property
        def include(self):
            href = self.element.xi_href
            if href is not None:
                return types.value(repr(href))

        @property
        def format(self):
            return self.element.xi_parse

    node = property(Node)

    xi_href = None
    xi_parse = None

class MockMetaElement(MockElement, translation.MetaElement):
    pass

class MockXiElement(MockElement):
    xi_href = utils.attribute('href')
    xi_parse = utils.attribute("parse", default="xml")

class MockParser(etree.Parser):
    element_mapping = {
        config.XHTML_NS: {None: MockElement},
        config.META_NS: {None: MockMetaElement},
        config.XI_NS: {None: MockXiElement}}

    fallback = MockElement
    
mock_parser = MockParser()

class MockMacros(template.Macros):
    def __getitem__(self, name):
        return self.get_macro(name)

class MockTemplate(object):
    def __init__(self, body, parser=mock_parser, doctype=None):
        self.body = body
        self.parser = parser
        self.doctype = doctype
        
    @property
    def macros(self):
        def render(name, slots={}, parameters={}):
            parameters[config.SYMBOLS.slots] = slots
            func = compile_template(
                self.parser, self.parser.parse, self.body,
                macro=name, global_scope=False, **parameters)
            return func(**parameters)
        return MockMacros(render)

    def render(self, **kwargs):
        func = compile_template(
            self.parser, self.parser.parse, self.body,
            explicit_doctype=self.doctype, **kwargs)
        return func(**kwargs)

    __call__ = render
