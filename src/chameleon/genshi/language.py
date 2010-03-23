from chameleon.core import translation
from chameleon.core import generation
from chameleon.core import config
from chameleon.core import etree
from chameleon.core import utils
from chameleon.core import types

import expressions
import itertools

try:
    from lxml import html
except ImportError:
    html = None

def get_elements_with_attribute_unless_in_between(element, ns, name, discard):
    elements = []

    discarded = utils.elements_with_attribute(element, ns, discard)
    subelements = utils.elements_with_attribute(element, ns, name)

    for subelement in subelements:
        parent = subelement.getparent()
        while parent is not None:
            if parent in discarded:
                break
            parent = parent.getparent()
        else:
            elements.append(subelement)

    return elements

class XPathResult(list):
    def __unicode__(self):
        def format_result(result):
            if isinstance(result, basestring):
                return result
            return html.tostring(result)
        return u"".join(
            map(format_result, self))

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __html__(self):
        return unicode(self)

class MatchTemplates(object):
    encoding = 'utf-8'

    def __init__(self):
        self.templates = {}

    def __call__(self, path, limit):
        def outer(func):
            self.templates[path] = func, limit
            def inner(*args, **kwargs):
                return func(*args, **kwargs)
            return inner
        return outer

    def __nonzero__(self):
        return bool(self.templates)

    def process(self, body):
        if not self.templates:
            return body

        if html is None:
            raise ImportError("lxml.html")

        root = html.fromstring(body)
        for path, (method, limit) in self.templates.items():
            for element in root.xpath(path)[:limit]:
                out, write = generation.initialize_stream()
                def select(path):
                    return XPathResult(element.xpath(path))
                method(out, write, select)

                # replace element with fragments
                fragments = html.fragments_fromstring(out.getvalue())
                if element is root:
                    for fragment in fragments:
                        # ignore trivial fragments, if we're replacing
                        # the root node
                        if isinstance(fragment, basestring):
                            if fragment.strip('\n ') == "":
                                continue
                            raise ValueError(
                                "Must replace root with structural element.")

                        prev = root = fragment
                else:
                    # this node does have a parent; replace it with
                    # the fragments
                    tail = element.tail
                    prev = element.getprevious()
                    parent = element.getparent()
                    index = parent.index(element)

                    fragment = fragments[0]
                    if isinstance(fragment, basestring):
                        if prev is None:
                            parent.text = (parent.text or "") + fragment
                        else:
                            prev.tail = (prev.tail or "") + fragment
                        fragments.pop(0)

                    for fragment in fragments:
                        if isinstance(fragment, basestring):
                            assert prev is not None
                            prev.tail = (prev.tail or "") + fragment
                        else:
                            parent.insert(index+1, fragment)
                            prev = fragment

                    parent.remove(element)
                    if prev is None:
                        parent.text += tail
                    else:
                        prev.tail = tail

        return html.tostring(root, pretty_print=True, encoding=self.encoding)

class GenshiElement(translation.Element):
    """Genshi language element."""

    translator = expressions.translator
    strip_text = False

    class node(translation.Node):
        ns_omit = (
            "http://xml.zope.org/namespaces/meta",
            "http://xml.zope.org/namespaces/i18n",
            "http://www.w3.org/2001/XInclude",
            "http://genshi.edgewall.org/")

        match_symbol = "match_templates"
        markup_symbol = "_markup"

        symbols = translation.Node.symbols(
            match_templates=config.TRANSIENT_SYMBOL)

        @property
        def _interpolation_enabled(self):
            return self.element.meta_interpolation in config.TRUEVALS + ('',)

        @property
        def _interpolation_escape(self):
            return self.element.meta_interpolation_escaping in config.TRUEVALS + ('',)

        @property
        def omit(self):
            if self.element.py_strip is not None:
                return self.element.py_strip or True
            if self.element.meta_omit is not None:
                return self.element.meta_omit or True
            if self.element.py_replace or self.element.meta_replace:
                return True
            if self.element.xi_href:
                return True

        @property
        def define(self):
            return self.element.py_with

        @property
        def condition(self):
            return self.element.py_if

        @property
        def repeat(self):
            return self.element.py_for

        @property
        def content(self):
            return self.element.py_content or self.element.py_replace or \
                   self.element.meta_replace

        @property
        def skip(self):
            return bool(self.content) or self.translate is not None

        @property
        def dict_attributes(self):
            return self.element.py_attrs

        @property
        def dynamic_attributes(self):
            attributes = []

            py_attributes = utils.get_attributes_from_namespace(
                self.element, config.PY_NS)
            meta_attributes = utils.get_attributes_from_namespace(
                self.element, config.META_NS)
            i18n_attributes = utils.get_attributes_from_namespace(
                self.element, config.I18N_NS)

            internal = tuple(itertools.chain(
                py_attributes, meta_attributes, i18n_attributes))

            if self._interpolation_enabled:
                attributes.extend(self.interpolated_attributes(internal))

            if self.element.meta_attributes is not None:
                attributes.extend(self.element.meta_attributes)

            if len(attributes) > 0:
                return attributes

        @property
        def macro(self):
            if self.element.py_match is not None:
                if self.match_symbol not in itertools.chain(
                    *self.element.stream.scope):
                    raise NameError(self.match_symbol)
                symbols = self.element.stream.symbols
                args = symbols.out, symbols.write, "select"
                if self.element.py_once.lower() in config.TRUEVALS:
                    once = 1
                else:
                    once = repr(None)
                decorator = '%s("""%s""", %s)' % (
                    self.match_symbol, self.element.py_match, once)
                return types.method(
                    "match", args, decorators=(decorator,))

            return self.element.py_def

        @property
        def translated_attributes(self):
            return self.element.i18n_attributes

        @property
        def translate(self):
            return self.element.i18n_translate

        @property
        def translation_name(self):
            return self.element.i18n_name

        @property
        def translation_domain(self):
            return self.element.i18n_domain

        @property
        def cdata(self):
            return self.element.meta_cdata

        @property
        def include(self):
            href = self.element.xi_href
            if href is not None:
                return types.join(self.element.translator.split(href))

        @property
        def format(self):
            return self.element.xi_parse

        @property
        def text(self):
            text = self.element.text
            if text is not None:
                parent = self.element.getparent()
                if parent is not None and self.element.strip_text and parent[0] is self.element:
                    text = text.lstrip('\n ')

                if not self._interpolation_enabled:
                    return (text,)

                parts = self.element.translator.split(text)
                if self.element.tag == '{http://www.w3.org/1999/xhtml}cdata':
                    return parts

                if not self._interpolation_escape:
                    return parts

                return tuple(
                    isinstance(part, types.expression) and types.escape(part) or \
                    self.element.meta_structure is True and part or \
                    utils.htmlescape(part) for part in parts)

            return ()

        @property
        def tail(self):
            tail = self.element.tail
            if tail is not None:
                if self.element.strip_text:
                    parent = self.element.getparent()
                    if parent is not None and parent.strip_text and parent[-1] is self.element:
                        tail = tail.rstrip('\n ')

                parent = self.element.getparent()
                if parent is not None and not parent.node._interpolation_enabled:
                    return (tail,)

                parts = self.element.translator.split(tail)
                if self.element.tag == '{http://www.w3.org/1999/xhtml}cdata':
                    return parts

                if not self._interpolation_escape:
                    return parts

                return tuple(
                    isinstance(part, types.expression) and types.escape(part) or \
                    self.element.meta_structure is True and part or \
                    utils.htmlescape(part) for part in parts)

            return ()

    node = property(node)

    def update(self):
        # Step 1: Convert py:choose, py:when, py:otherwise into
        # tal:define, tal:condition
        stream = self.stream
        choose_expression = self._pull_attribute(utils.py_attr('choose'))
        if choose_expression is not None:
            choose_variable = stream.new_var()
            
            if choose_expression:
                self._add_define(choose_variable, choose_expression)
                
            # select all elements that have the "py:when" controller,
            # unless a "py:choose" expression sits in-between
            elements = get_elements_with_attribute_unless_in_between(
                self, config.PY_NS, "when", "choose")

            variables = []
            for element in elements:
                expression = element._pull_attribute(utils.py_attr('when'))
                variable = stream.new_var()
                variables.append(variable)

                # add definition to ancestor
                self._add_define(variable, expression)

                # add condition to element
                if choose_expression:
                    expression = "%s == %s" % (
                        choose_variable, variable)
                else:
                    expression = "%s" % variable

                element.attrib[utils.py_attr('if')] = expression

            # process any "py:otherwise"-controllers
            elements = get_elements_with_attribute_unless_in_between(
                self, config.PY_NS, "otherwise", "choose")

            for element in elements:
                if choose_expression:
                    expression = "%s not in %s" % (
                        choose_variable, repr(tuple(variables)))
                else:
                    expression = "not(%s)" % " or ".join(variables)

                element.attrib[utils.py_attr('if')] = expression

    def _add_define(self, variable, expression):
        name = utils.py_attr('with')
        define = "%s=%s; " % (variable, expression)

        if name in self.attrib:
            self.attrib[name] += define
        else:
            self.attrib[name] = define

    def _pull_attribute(self, name, default=None):
        attrib = self.attrib
        if name in attrib:
            value = attrib[name]
            del attrib[name]
            return value
        return default

    xi_href = None
    xi_parse = None
    py_once = "false"

class XHTMLElement(GenshiElement):
    """XHTML namespace element."""

    py_if = utils.attribute(
        utils.py_attr('if'), lambda p: p.expression)
    py_for = utils.attribute(
        utils.py_attr('for'), lambda p: p.definition)
    py_with = utils.attribute(utils.py_attr('with'),
        lambda p: expressions.translator.definitions)
    py_choose = utils.attribute(
        utils.py_attr('choose'), lambda p: p.expression)
    py_when = utils.attribute(
        utils.py_attr('when'), lambda p: p.expression)
    py_otherwise = utils.attribute(
        utils.py_attr('otherwise'), lambda p: p.expression)
    py_match = utils.attribute(
        utils.py_attr('match'))
    py_once = utils.attribute(
        utils.py_attr('once'), default='false')
    py_def = utils.attribute(
        utils.py_attr('def'), lambda p: p.method)
    py_attrs = utils.attribute(
        utils.py_attr('attrs'), lambda p: p.expression)
    py_content = utils.attribute(
        utils.py_attr('content'), lambda p: p.output)
    py_replace = utils.attribute(
        utils.py_attr('replace'), lambda p: p.output)
    py_strip = utils.attribute(
        utils.py_attr('strip'), lambda p: p.expression)
    meta_translator = etree.Annotation(
        utils.meta_attr('translator'))
    meta_interpolation = utils.attribute(
        utils.meta_attr('interpolation'), default='true', recursive=True)
    meta_interpolation_escaping = utils.attribute(
        utils.meta_attr('interpolation-escaping'), default='true', recursive=True)
    i18n_translate = utils.attribute(
        utils.i18n_attr('translate'))
    i18n_attributes = utils.attribute(
        utils.i18n_attr('attributes'), lambda p: p.mapping)
    i18n_domain = utils.attribute(
        utils.i18n_attr('domain'))
    i18n_name = utils.attribute(
        utils.i18n_attr('name'))

class MetaElement(XHTMLElement, translation.MetaElement):
    pass

class PyElement(XHTMLElement):
    strip_text = True
    py_strip = utils.attribute("strip", lambda p: p.expression, u"")

class PyIfElement(PyElement):
    py_if = utils.attribute("test", lambda p: p.expression)

class PyForElement(PyElement):
    py_for = utils.attribute("each", lambda p: p.definition)

class PyWithElement(PyElement):
    py_with = utils.attribute(
        "vars", lambda p: expressions.translator.definitions)

class PyDefElement(PyElement):
    py_def = utils.attribute("function", lambda p: p.method)

class PyMatchElement(PyElement):
    py_match = utils.attribute("path")
    py_once = utils.attribute("once", default="false")

class XiIncludeElement(XHTMLElement):
    xi_href = utils.attribute("href")
    xi_parse = utils.attribute("parse", default="xml")

class TextElement(XHTMLElement):
    meta_interpolation_escaping = False

class Parser(etree.Parser):
    """The parser implementation for Genshi templates."""

    element_mapping = {
        config.XHTML_NS: {None: XHTMLElement},
        config.META_NS: {None: MetaElement},
        config.XI_NS: {'include': XiIncludeElement},
        config.PY_NS: {'if': PyIfElement,
                       'for': PyForElement,
                       'def': PyDefElement,
                       'with': PyWithElement,
                       'match': PyMatchElement}}

    fallback = XHTMLElement

class TextParser(Parser):
    element_mapping = {
        config.XHTML_NS: {None: TextElement},
        }
