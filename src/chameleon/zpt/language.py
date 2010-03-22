import itertools

from chameleon.core import translation
from chameleon.core import config
from chameleon.core import etree
from chameleon.core import types
from chameleon.core import utils

import expressions

class ZopePageTemplateElement(translation.Element):
    """Zope Page Template element.

    Implements the ZPT subset of the attribute template language.
    """

    strip_text = False

    class node(translation.Node):
        symbols = translation.Node.symbols(
            macros=config.TRANSIENT_SYMBOL)

        content_symbol = '_content'

        ns_omit = (
            "http://xml.zope.org/namespaces/meta",
            "http://xml.zope.org/namespaces/tal",
            "http://xml.zope.org/namespaces/metal",
            "http://xml.zope.org/namespaces/i18n")

        @property
        def _interpolation_enabled(self):
            return self.element.meta_interpolation in config.TRUEVALS + ('',)

        @property
        def _interpolation_escape(self):
            return self.element.meta_interpolation_escaping in config.TRUEVALS + ('',)

        @property
        def omit(self):
            if self.element.tal_omit is not None:
                return self.element.tal_omit or True
            if self.element.meta_omit is not None:
                return self.element.meta_omit or True
            if self.element.tal_replace or self.element.meta_replace:
                return True
            if self.element.metal_use or self.element.metal_extend:
                return True

        @property
        def define(self):
            return self.element.tal_define

        @property
        def assign(self):
            content = self._content
            if content is not None:
                definition = (
                    types.declaration((self.content_symbol,)),
                    content)
                return types.definitions((definition,))

        @property
        def condition(self):
            return self.element.tal_condition

        @property
        def repeat(self):
            return self.element.tal_repeat

        @property
        def content(self):
            content = self._content
            if content is not None:
                if isinstance(content, types.escape):
                    return types.escape((types.value(self.content_symbol),))
                return types.parts((types.value(self.content_symbol),))

        @property
        def _content(self):
            return (self.element.tal_content or
                    self.element.tal_replace or
                    self.element.meta_replace)

        @property
        def skip(self):
            return (bool(self.content) or
                    bool(self.use_macro) or
                    bool(self.extend_macro) or
                    self.translate is not None)

        @property
        def dynamic_attributes(self):
            attributes = []

            tal_attributes = utils.get_attributes_from_namespace(
                self.element, config.TAL_NS)
            metal_attributes = utils.get_attributes_from_namespace(
                self.element, config.METAL_NS)
            meta_attributes = utils.get_attributes_from_namespace(
                self.element, config.META_NS)
            i18n_attributes = utils.get_attributes_from_namespace(
                self.element, config.I18N_NS)

            internal = tuple(itertools.chain(
                tal_attributes, metal_attributes, meta_attributes, i18n_attributes))

            if self._interpolation_enabled:
                attributes.extend(self.interpolated_attributes(internal))

            if self.element.tal_attributes is not None:
                attributes.extend(self.element.tal_attributes)

            if self.element.meta_attributes is not None:
                attributes.extend(self.element.meta_attributes)

            if len(attributes) > 0:
                return attributes

        @property
        def translated_attributes(self):
            return self.element.i18n_attributes

        @property
        def translate(self):
            return self.element.i18n_translate

        @property
        def translation_name(self):
            parent = self.element.getparent()
            if parent is not None and parent.node.translate is not None:
                return self.element.i18n_name

        @property
        def translation_domain(self):
            return self.element.i18n_domain

        @property
        def use_macro(self):
            return self.element.metal_use

        @property
        def define_macro(self):
            return self.element.metal_define

        @property
        def extend_macro(self):
            return self.element.metal_extend

        @property
        def define_slot(self):
            return self.element.metal_defineslot

        @property
        def fill_slot(self):
            return self.element.metal_fillslot

        @property
        def cdata(self):
            return self.element.meta_cdata

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

    @property
    def translator(self):
        element = self.root
        if element is None:
            raise ValueError("Default expression not set.")

        return expressions.lookup_translator(None, element.meta_translator)

    metal_define = None
    metal_use = None
    metal_extend = None
    metal_fillslot = None
    metal_defineslot = None

    i18n_name = None
    i18n_domain = None
    i18n_translate = None
    i18n_attributes = None

    tal_define = None
    tal_condition = None
    tal_replace = None
    tal_content = None
    tal_repeat = None
    tal_attributes = None

    meta_translator = etree.Annotation(
        utils.meta_attr('translator'))
    meta_interpolation = utils.attribute(
        utils.meta_attr('interpolation'), default='true', recursive=True)
    meta_interpolation_escaping = utils.attribute(
        utils.meta_attr('interpolation-escaping'), default='true', recursive=True)

class XHTMLElement(ZopePageTemplateElement):
    """XHTML namespace element."""

    tal_define = utils.attribute(
        utils.tal_attr('define'), lambda p: p.definitions)
    tal_condition = utils.attribute(
        utils.tal_attr('condition'), lambda p: p.tales)
    tal_repeat = utils.attribute(
        utils.tal_attr('repeat'), lambda p: p.definition)
    tal_attributes = utils.attribute(
        utils.tal_attr('attributes'), lambda p: p.definitions)
    tal_content = utils.attribute(
        utils.tal_attr('content'), lambda p: p.output)
    tal_replace = utils.attribute(
        utils.tal_attr('replace'), lambda p: p.output)
    tal_omit = utils.attribute(
        utils.tal_attr('omit-tag'), lambda p: p.tales)
    tal_default_expression = utils.attribute(
        utils.tal_attr('default-expression'), encoding='ascii')
    metal_define = utils.attribute(
        utils.metal_attr('define-macro'))
    metal_use = utils.attribute(
        utils.metal_attr('use-macro'), lambda p: p.tales)
    metal_extend = utils.attribute(
        utils.metal_attr('extend-macro'), lambda p: p.tales)
    metal_fillslot = utils.attribute(
        utils.metal_attr('fill-slot'))
    metal_defineslot = utils.attribute(
        utils.metal_attr('define-slot'))
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

class TALElement(XHTMLElement):
    """TAL namespace element."""

    strip_text = True
    
    tal_define = utils.attribute(
        ("define", utils.tal_attr("define")), lambda p: p.definitions)
    tal_condition = utils.attribute(
        ("condition", utils.tal_attr("condition")), lambda p: p.tales)
    tal_replace = utils.attribute(
        ("replace", utils.tal_attr("replace")), lambda p: p.output)
    tal_repeat = utils.attribute(
        ("repeat", utils.tal_attr("repeat")), lambda p: p.definition)
    tal_attributes = utils.attribute(
        ("attributes", utils.tal_attr("attributes")),
        lambda p: utils.raise_exc(
            TypeError("Dynamic attributes not allowed on "
                      "elements with TAL-namespace.")))
    tal_content = utils.attribute(
        ("content", utils.tal_attr("content")), lambda p: p.output)
    tal_omit = utils.attribute(
        ("omit-tag", utils.tal_attr("omit-tag")), lambda p: p.tales, u"")    

class METALElement(XHTMLElement):
    """METAL namespace element."""

    strip_text = True
    tal_omit = True
    
    metal_define = utils.attribute(
        ("define-macro", utils.metal_attr("define-macro")))
    metal_use = utils.attribute(
        ('use-macro', utils.metal_attr('use-macro')), lambda p: p.tales)
    metal_extend = utils.attribute(
        ('extend-macro', utils.metal_attr('extend-macro')), lambda p: p.tales)
    metal_fillslot = utils.attribute(
        ('fill-slot', utils.metal_attr('fill-slot')))
    metal_defineslot = utils.attribute(
        ('define-slot', utils.metal_attr('define-slot')))

class TextElement(XHTMLElement):
    meta_interpolation_escaping = False

class Parser(etree.Parser):
    """Zope Page Template parser."""
    
    element_mapping = {
        config.XHTML_NS: {None: XHTMLElement},
        config.META_NS: {None: MetaElement},
        config.TAL_NS: {None: TALElement},
        config.METAL_NS: {None: METALElement}}

    fallback = XHTMLElement
    
    default_expression = 'python'

    def __init__(self, default_expression=None):
        if default_expression is not None:
            self.default_expression = default_expression

    def parse(self, body):
        tree = super(Parser, self).parse(body)
        tree.getroot().meta_translator = self.default_expression
        return tree

    def validate(self, element):
        kls = element.__class__
        if kls.metal_use.get(element) and kls.metal_define.get(element):
            raise SyntaxError(
                "Cannot use `define-macro` with `use-macro`; use "
                "`extend-macro` instead.")


class TextParser(Parser):
    """Parser for text templates."""

    element_mapping = {
        config.XHTML_NS: {None: TextElement},
    }

