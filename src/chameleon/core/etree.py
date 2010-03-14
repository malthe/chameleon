import config
import utils
import base64
import re

import xml.parsers.expat

from cPickle import dumps, loads
from StringIO import StringIO

re_tag_start = re.compile(r'<(?!!)')
marker = object()

def parse(body, parser, validator):
    """Parse XML document using expat and return an
    ElementTree-compatible document tree."""
    
    junk = ""
    tree = None
    parts = []

    offset = 0
    original_body = body
    
    while tree is None:
        expat = xml.parsers.expat.ParserCreate()
        expatparser = ExpatParser(parser, body, expat, validator)
        
        try:
            # attempt to parse this body; if we're not successful,
            # this may be because the document source consists of
            # several 'parts'; although this is not valid XML, we do
            # support it, being a template engine, not a XML
            # validator :-)
            if body is not None:
                expat.Parse(body, 1)

            root = expatparser.root
            if parts:
                if root is not None:
                    parts.append(root)
                root = parser.makeelement(
                    utils.meta_attr('fragments'))
                for i, part in enumerate(parts):
                    if isinstance(part, basestring):
                        parts[i-1].tail = part
                    else:
                        root.append(part)
                tree = root.getroottree()
            elif root is not None:
                tree = root.getroottree()
            else:
                raise RuntimeError("Unexpected parsing error.")

        except xml.parsers.expat.ExpatError, e:
            offset += expat.CurrentByteIndex

            # if we are not able to find a tree root, we give up and
            # let the exception through; if the error status code is 3
            # (no element found) and we've already parsed some parts,
            # we ignore the error and stop parsing.
            code = getattr(e, 'code', -1)
            if code == 3:
                body = None

                if parts:
                    continue

                raise

            if code == 9 and expatparser.root is not None:
                # add the root as a tree fragment and update the body
                # source to the next possible chunk
                parts.append(expatparser.root)
                body = body[:expatparser.index] + body[expat.CurrentByteIndex:]

                # a simple heuristic is used here to allow chunks of
                # 'junk' in-between the tree fragments
                m = re_tag_start.search(body)
                if m is not None:
                    pos = m.start()
                else:
                    pos = -1
                junk = body[:pos]
                body = body[pos:]
                parts.append(junk)
                offset += pos
            else:
                # the default exception won't provide correct
                # information about where in the document the
                # exception stems from; we can compute it manually
                # though.
                line = original_body[:offset].count('\n') + 1
                column = offset - original_body[:offset].rfind('\n')
                error_msg = str(e).split(':')[0]
                error_msg = "%s: line %d, column %d" % (
                    error_msg, line, column)
                raise xml.parsers.expat.ExpatError(error_msg)

    return tree, expatparser.doctype

class ExpatParser(object):
    """XML tree parser using the ``xml.parsers.expat`` stream
    parser. This parser serve to accept template input which lacks a
    proper prefix namespace mapping or entity definitions. It also
    works around an issue where the expat parser incorrectly parses an
    element with trivial body text as self-closing."""
    
    root = None
    index = None
    
    # doctype
    _doctype = doctype = None

    # xml-declaration
    xml_version = None
    encoding = None
    standalone = None
    parsing_external_entities = False
    
    def __init__(self, parser, body, expat, validator):
        self.parser = parser
        self.body = body
        self.expat = expat
        self._validate = validator

        # set up expat parser
        expat.ordered_attributes = 1
        expat.UseForeignDTD()
        expat.SetParamEntityParsing(
            xml.parsers.expat.XML_PARAM_ENTITY_PARSING_ALWAYS)

        # attach expat parser methods
        for name, value in type(self).__dict__.items():
            if isinstance(value, property):
                continue
            try:
                setattr(expat, name, getattr(self, name))
            except AttributeError:
                pass

    def _get_element(self):
        try:
            return self._element
        except AttributeError:
            raise xml.parsers.expat.ExpatError(
                "Unable to parse document; no start-tag found.")

    def _set_element(self, element):
        self._element = element

    element = property(_get_element, _set_element)

    def _validate(self, element):
        pass
    
    def StartElementHandler(self, tag, attributes):
        attrs = utils.odict()
        while attributes:
            key = attributes.pop(0)
            value = attributes.pop(0)
            attrs[key] = value
        
        # update prefix to namespace mapping
        if self.root is None:
            self.index = self.expat.CurrentByteIndex
            nsmap = utils.odict()
        else:
            nsmap = self.root.nsmap.copy()

        # process namespace declarations
        for key, value in attrs.items():
            if key.startswith('xmlns:'):
                prefix, name = key.split(':')
                nsmap[name] = value
                del attrs[key]

        for key, value in attrs.items():
            try:
                prefix, name = key.split(':')
            except (ValueError, TypeError):
                continue

            del attrs[key]

            namespace = nsmap.get(prefix)
            if namespace is None:
                if self.root is not None:
                    element = self.element

                    while element is not None:
                        namespace = element.nsmap.get(prefix)
                        if namespace is not None:
                            nsmap[prefix] = namespace
                            break
                        element = element.getparent()

                if namespace is None:
                    try:
                        namespace = config.DEFAULT_NS_MAP[prefix]
                    except KeyError:
                        raise KeyError(
                            "Attribute prefix unknown: '%s'." % prefix)

            attrs['{%s}%s' % (namespace, name)] = value

        # process tag
        try:
            prefix, name = tag.split(':')
            namespace = nsmap.get(prefix) or config.DEFAULT_NS_MAP[prefix]
            tag = '{%s}%s' % (namespace, name)
        except ValueError:
            pass

        # create element using parser
        element = self.parser.makeelement(tag, attrs, nsmap=nsmap)

        if self.root is None:
            # cook doctype
            doctype = []
            if (self._doctype is not None and
                self._doctype["pubid"] is None and
                self._doctype["sysid"] is None and
                self._doctype["has_internal_subset"] and
                self._doctype["entities"]):
                doctype.append("<!DOCTYPE %(doctype_name)s [" % self._doctype)
                for entity, repl in self._doctype["entities"]:
                    doctype.append('<!ENTITY %s "%s">' % (
                        entity,
                        repl.encode("ascii", "xmlcharrefreplace")))
                doctype.append("]>")
            elif self._doctype:
                d = self._doctype
                if d['pubid'] is None or d['sysid'] is None:
                    doctype.append(
                        '<!DOCTYPE %(doctype_name)s>' % d)
                else:
                    doctype.append(
                        '<!DOCTYPE %(doctype_name)s PUBLIC '
                        '"%(pubid)s" "%(sysid)s">' % d)
            self.doctype = "\n".join(doctype).encode("utf-8")

            ElementTree(
                self.parser, element, self.xml_version,
                self.encoding, self.standalone,
                self.doctype)

            # set this element as tree root
            self.root = element
        else:
            self.element.append(element)

        # validate element
        self._validate(element)

        # set as current element
        self.element = element

    def EndElementHandler(self, name):
        if self.element.text is None and self.body[
            self.expat.CurrentByteIndex-2] != '/':
            self.element.text = ""
        self.element = self.element.getparent()

    def CharacterDataHandler(self, data):
        """Process ``data`` while comparing to input context to check
        for HTML entities (which must be preserved)."""

        
        context = self.body[self.expat.CurrentByteIndex:]
        text = u""

        while data:
            m = utils.re_entity.search(context)
            if m is None or m.start() >= len(data):
                text += data
                break

            n = utils.re_entity.match(data)
            if n is not None:
                length = n.end()
            else:
                length = 1

            text += context[0:m.end()]
            context = context[m.end():]
            data = data[m.start()+length:]
            
        if len(self.element) == 0:
            current = self.element.text or ""
            self.element.text = current + text
        else:
            current = self.element[-1].tail or ""
            self.element[-1].tail = current + text
            
    def ProcessingInstructionHandler(self, target, data):
        self.element.append(
            self.parser.makeprocessinginstruction(target, data))

    def StartCdataSectionHandler(self):
        element = self.parser.makeelement(
            utils.xhtml_attr('cdata'))
        element.meta_cdata = ""
        self.element.append(element)
        self.element = element            

    def EndCdataSectionHandler(self):
        self.element = self.element.getparent()

    def CommentHandler(self, text):
        if self.root is not None and self.element is not None:
            self.element.append(
                self.parser.makecomment(text))

    def XmlDeclHandler(self, xml_version, encoding, standalone):
        self.xml_version = xml_version
        self.encoding = encoding

        if standalone:
            self.standalone = 'yes'
        else:
            self.standalone = 'no'
        
    def ExternalEntityRefHandler(self, context, base, sysid, pubid):
        self.parsing_external_entities = True
        try:
            parser = self.expat.ExternalEntityParserCreate(context)
            parser.ProcessingInstructionHandler = self.ProcessingInstructionHandler
            parser.ParseFile(StringIO(utils.entities))
            return 1
        finally:
            self.parsing_external_entities = False

    def DefaultHandler(self, userdata):
        if userdata.startswith('&'):
            return self.CharacterDataHandler(userdata)            
                
    def StartDoctypeDeclHandler(self, *args):
        doctype_name, sysid, pubid, has_internal_subset = args
        self.has_internal_subset = has_internal_subset
        self._doctype = {"doctype_name" : doctype_name,
                         "sysid": sysid,
                         "pubid": pubid,
                         "has_internal_subset": has_internal_subset,
                         "entities": []}

    def EntityDeclHandler(self, *args):
        if self.parsing_external_entities:
            return
        if self._doctype is not None and self._doctype["has_internal_subset"]:
            (entityName, is_parameter_entity, value,
             base, systemId, publicId, notationName) = args
            if value is not None:
                self._doctype["entities"].append((entityName, value))

class Parser(object):
    element_mapping = utils.emptydict
    fallback = None
    
    def parse_xml(self, body):
        return self.parse(body)
    
    def parse_text(self, text):
        tree = self.parse('<meta xmlns="%s"></meta>' % config.META_NS)
        tree.getroot().text = text
        tree.getroot().meta_omit = ""
        tree.getroot().meta_structure = True
        return tree

    def parse(self, body):
        lookup = ElementNamespaceClassLookup(
            fallback=ElementDefaultClassLookup(self.fallback))
        for key, mapping in self.element_mapping.items():
            lookup.get_namespace(key).update(mapping)

        parser = XMLParser(resolve_entities=False, strip_cdata=False)
        parser.setElementClassLookup(lookup)

        tree, self.doctype = parse(body, parser, self.validate)
        return tree

    def validate(self, element):
        pass

    # for backwards-compatibility, the parser object must be callable
    # which invokes the ``parse``-method
    def __call__(self, body):
        return self.parse(body)

class Annotation(property):
    def __init__(self, name, default=None):
        property.__init__(self, self._get, self._set)
        self.name = name
        self.default = default

    def _get(instance, element):
        value = element.attrib.get(instance.name)
        if value is None:
            return instance.default
        if value:
            value = loads(base64.decodestring(value))
        return value

    def _set(instance, element, value):
        element.attrib[instance.name] = base64.encodestring(dumps(value))

class ElementBase(object):
    """ElementTree-compatible base element."""

    node = tree = parent = prefix = tail = text = None

    def __init__(self, tag, attrib=None, nsmap=None):
        if attrib is None:
            attrib = {}
        if nsmap is None:
            nsmap = {}

        self.children = []
        self.tag = tag
        self.attrib = attrib
        self.nsmap = nsmap

        if '}' in tag:
            namespace = tag[1:].split('}')[0]
        else:
            namespace = attrib.get('xmlns')

        for prefix, ns in nsmap.items() + config.DEFAULT_NS_MAP.items():
            if namespace == ns:
                self.prefix = prefix
                break

    def append(self, element):
        self.children.append(element)
        self.register(element)

    def insert(self, index, element):
        self.children.insert(index, element)
        self.register(element)

    def remove(self, element):
        self.children.remove(element)
        element.parent = element.tree = None

    def register(self, element):
        element.parent = self
        
        # if we're appending an element rooted to an element tree,
        # we'll let the current element take over that tree.
        if self.tree is None and element.tree is not None:
            self.tree = element.tree
            self.tree.root = self
            
        # inherit tree reference
        element.tree = self.tree

    def index(self, element):
        return self.children.index(element)

    def getchildren(self):
        return self.children
    
    def getparent(self):
        return self.parent

    def getroottree(self):
        if self.tree is None:
            parent = self.getparent()
            if parent is None:
                raise RuntimeError("Unable to locate root; element has no parent.")
            return parent.getroottree()
        return self.tree

    @property
    def makeelement(self):
        tree = self.getroottree()
        return tree.parser.makeelement

    def tag(self):
        return utils.serialize(self)

    def walk(self):
        yield self
        for child in self:
            for element in child.walk():
                yield element

    def __len__(self):
        return len(self.children)
    
    def __iter__(self):
        return iter(self.children)

    def __getitem__(self, key):
        return self.children[key]

    def __str__(self):
        return str(unicode(self))

    def __unicode__(self):
        return self.tag()

class ProcessingInstructionElement(ElementBase):
    attrib = {}
    children = ()
    
    def __init__(self, target, data):
        self.target = target
        self.data = data

    def tag(self):
        return u"<?%s %s?>" % (self.target, self.data)

class CommentElement(ElementBase):
    """XML comment.

    This element is modelled after the ``lxml`` comment element; the
    ``tag`` attribute should be a method that renders the comment.
    """
    
    tail = None
    attrib = {}
    children = ()
    
    def __init__(self, text):
        self.text = text

    def tag(self):
        return u"<!--%s-->" % self.text

class ElementTree(object):
    """ElementTree-compatible tree element."""

    def __init__(self, parser, root, xml_version=None, encoding=None,
                 standalone=None, doctype=None):
        if doctype is None:
            doctype = {}

        self.docinfo = DocInfo(xml_version, encoding, standalone, doctype)
        self.parser = parser
        self.root = root
        
        root.tree = self
        
    def getroot(self):
        return self.root
        
class XMLParser(object):
    """XML parser class."""
    
    def __init__(self, resolve_entities=True, strip_cdata=True):
        self.resolve_entities = resolve_entities
        self.strip_cdata = strip_cdata

    def setElementClassLookup(self, lookup):
        self.lookup = lookup

    @property
    def makeelement(self):
        return self.lookup.makeelement

    @property
    def makeprocessinginstruction(self):
        return ProcessingInstructionElement

    @property
    def makecomment(self):
        return CommentElement

class ElementNamespaceClassLookup(object):
    def __init__(self, fallback=None):
        self.fallback = fallback
        self.by_namespace = {}
        
    def get_namespace(self, key):
        return self.by_namespace.setdefault(key, {})

    def makeelement(self, tag, attrs=None, nsmap=None):
        if '}' in tag:
            namespace, name = tag[1:].split('}')
        else:
            namespace, name = None, tag
            
        mapping = self.get_namespace(namespace)
        
        element_class = mapping.get(name) or mapping.get(None)
        if element_class is not None:
            return element_class(tag, attrs, nsmap=nsmap)

        return self.fallback.makeelement(tag, attrs, nsmap=nsmap)

class ElementDefaultClassLookup(object):
    def __init__(self, element_class):
        self.makeelement = element_class

class DocInfo(object):
    """XML document information class."""

    def __init__(self, xml_version, encoding, standalone, doctype):
        self.xml_version = xml_version
        self.encoding = encoding
        self.standalone = standalone
        self.doctype = doctype
