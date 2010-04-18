from StringIO import StringIO
from cPickle import dumps

try:
    from hashlib import sha1 as sha
except ImportError:
    from sha import sha

try:
    import codegen
except ImportError:
    codegen = None

import generation
import clauses
import itertools
import types
import utils
import etree
import config
import copy
import i18n

GLOBALS = globals()

class Node(object):
    """Element translation class.

    This class implements the translation node for an element in the
    template document tree.

    It's used internally by the translation machinery.
    """

    symbols = config.SYMBOLS

    translate = None
    translation_name = None
    translation_domain = None
    translated_attributes = None
    skip = None
    cdata = None
    omit = None
    assign = None
    define = None
    macro = None
    use_macro = None
    extend_macro = None
    define_macro = None
    fill_slot = None
    define_slot = None
    condition = None
    repeat = None
    content = None
    include = None
    format = None
    dict_attributes = None
    dynamic_attributes = utils.emptydict

    ns_omit = "http://xml.zope.org/namespaces/meta",

    def __init__(self, element):
        self.element = element

    @property
    def tag(self):
        tag = self.element.tag
        if '}' in tag:
            url, tag = tag[1:].split('}')
            for prefix, _url in self.element.nsmap.items():
                if prefix is not None and _url == url:
                    return "%s:%s" % (prefix, tag)
        return tag

    @property
    def stream(self):
        return self.element.stream

    @property
    def text(self):
        if self.element.text is None:
            return ()
        if self.element.meta_structure is True:
            return (self.element.text,)
        else:
            return (utils.htmlescape(self.element.text),)

    @property
    def tail(self):
        if self.element.tail is None:
            return ()
        if self.element.meta_structure is True:
            return (self.element.tail,)
        else:
            return (utils.htmlescape(self.element.tail),)

    @property
    def ns_attributes(self):
        prefix_omit = set()
        ns_omit = list(self.ns_omit)

        root = self.element.getroottree().getroot()
        if root is None or utils.get_namespace(root) == config.META_NS:
            ns_omit.append("http://www.w3.org/1999/xhtml")

        prefix_omit = set()
        namespaces = self.element.nsmap.values()

        parent = self.element.getparent()
        while parent is not None:
            for prefix, ns in parent.nsmap.items():
                if ns in namespaces:
                    prefix_omit.add(prefix)
            parent = parent.getparent()

        attrs = dict(
            ((prefix and "xmlns:%s" % prefix or "xmlns", ns)
             for (prefix, ns) in self.element.nsmap.items()
             if ns not in ns_omit and prefix not in prefix_omit))

        return attrs

    @property
    def static_attributes(self):
        result = {}
        element_ns = self.element.nsmap.get(self.element.prefix)

        nsmap = self.element.nsmap.copy()
        nsmap.update(config.DEFAULT_NS_MAP)

        root = self.element.getroottree().getroot()
        omit_default_prefix = root.meta_omit_default_prefix

        for prefix, ns in nsmap.items():
            if ns not in self.ns_omit:
                attrs = utils.get_attributes_from_namespace(self.element, ns)
                if prefix is None or ns == element_ns:
                    attrs.update(
                        utils.get_attributes_from_namespace(self.element, None))

                for tag, value in attrs.items():
                    name = tag.split('}')[-1]

                    if prefix and (ns != element_ns or not omit_default_prefix):
                        result["%s:%s" % (prefix, name)] = value
                    elif omit_default_prefix:
                        result[name] = value

        if self.element.prefix is None:
            result.update(
                utils.get_attributes_from_namespace(self.element, None))

        return result

    def interpolated_attributes(self, internal):
        for name, value in self.element.attrib.items():
            if name in internal:
                continue
            if '}' in name:
                namespace, name = name[1:].split('}')
                if namespace not in self.ns_omit:
                    for prefix, ns in self.element.nsmap.items():
                        if ns == namespace:
                            break
                    else:
                        continue
                    name = "%s:%s" % (prefix, name)
            parts = self.element.translator.split(value)
            for part in parts:
                if isinstance(part, types.expression):
                    yield types.declaration((name,)), types.join(parts)
                    break

    @property
    def attribute_ordering(self):
        static = self.static_attributes
        ns = self.ns_attributes

        names = list(ns)

        for key in self.element.attrib:
            name = utils.format_attribute(self.element, key)

            if name in static:
                names.append(name)

        # ensure that an "xmlns" attribute comes first
        names.sort(key=lambda name: name == 'xmlns', reverse=True)

        return names

    def update(self):
        self.element.update()

    def begin(self):
        self.stream.scope.append(set())
        self.stream.begin(self.serialize())

    def end(self):
        self.stream.end(self.serialize())
        self.stream.scope.pop()

    def body(self):
        if isinstance(self.skip, types.expression):
            assert isinstance(self.skip, types.value), \
                   "Dynamic skip condition can't be of type %s." % type(self.skip)
            condition = clauses.Condition(self.skip, invert=True)
            if len(self.element):
                condition.begin(self.stream)
        elif self.skip:
            return

        for element in self.element:
            element.node.update()

        for element in self.element:
            element.node.visit()

        if isinstance(self.skip, types.expression):
            if len(self.element):
                condition.end(self.stream)

    def visit(self):
        assert self.stream is not None, "Must use ``start`` method."

        for element in self.element:
            if not isinstance(element, Element):
                self.wrap_literal(element)

        self.update()
        self.begin()
        self.body()
        self.end()

    def serialize(self):
        """Serialize element into clause-statements."""

        _ = []

        # i18n domain
        if self.translation_domain is not None:
            _.append(clauses.Define(
                self.symbols.domain, types.value(repr(self.translation_domain))))

        # variable definitions
        adding = set()
        if self.define is not None:
            # as an optimization, we only define the `default`
            # symbol, if it's present in the definition clause (as
            # string representation)
            if self.symbols.default in repr(self.define):
                default = types.value(self.symbols.default_marker_symbol)
                _.append(clauses.Assign(default, self.symbols.default))

            for declaration, expression in self.define:
                if self.symbols.remote_scope in self.stream.scope[1]:
                    define = clauses.Define(
                        declaration, expression, self.symbols.remote_scope)
                else:
                    define = clauses.Define(declaration, expression)

                for name in define.declaration:
                    adding.add(name)

                _.append(define)

        # tag tail (deferred)
        tail = self.tail
        if self.fill_slot is None and self.translation_name is None:
            for part in reversed(tail):
                if isinstance(part, types.expression):
                    _.append(clauses.Write(part, defer=True))
                else:
                    _.append(clauses.Out(part, defer=True))

        # macro method
        macro = self.macro
        if macro is not None:
            if self.symbols.remote_scope in self.stream.scope[1]:
                dictionary = self.symbols.remote_scope
            else:
                dictionary = self.symbols.scope

            exclude = set((
                self.symbols.scope, self.symbols.slots)) | \
                self.stream.scope[0] | set(macro.args)

            scope = set(itertools.chain(*self.stream.scope[1:])) | set((
                self.symbols.out, self.symbols.write))

            args = tuple(macro.args) + tuple(
                "%s=%s" % (name, name) for name in scope if name not in exclude)

            _.append(clauses.Method(
                macro.name, args,
                decorators=macro.decorators,
                dictionary=dictionary))

        # condition
        if self.condition is not None:
            _.append(clauses.Condition(self.condition))

        # repeat
        if self.repeat is not None:
            variables, expression = self.repeat
            newline = True
            for element in self.element.walk():
                node = element.node
                if node and node.omit is False:
                    break
            else:
                newline = False

            if len(variables) > 1:
                repeat = clauses.Repeat(
                    variables, expression, repeatdict=False, newline=newline)
            else:
                repeat = clauses.Repeat(variables, expression, newline=newline)
            _.append(repeat)

        # assign
        if self.assign is not None:
            for declaration, expression in self.assign:
                if len(declaration) != 1:
                    raise ValueError("Can only assign single variable.")
                variable = declaration[0]
                _.append(clauses.Assign(expression, variable))

        content = self.content
        omit = self.omit

        if self.define_slot:
            name = self.define_slot
            scope = set(itertools.chain(*self.stream.scope[1:]))
            # assemble arguments that we pass into the macro
            # fill-slot callback
            exclude = set((self.symbols.scope,
                           self.symbols.slots,
                           self.symbols.out,
                           self.symbols.write)).union(self.stream.scope[0])

            scope_args = tuple(variable for variable in scope
                               if variable not in exclude)

            # look up fill-slot value
            _.append(clauses.Assign(
                types.template('%%(slots)s.get(%s)' % repr(name)),
                self.symbols.tmp))

            # if slot has been filled, either use it as is (if
            # it's a string), or pass in required arguments (if
            # it's a callback function)
            _.append(clauses.Condition(
                types.template('%(tmp)s is not None'),
                (clauses.Condition(
                    types.template('isinstance(%(tmp)s, basestring)'),
                    (clauses.Slot(
                        types.template("%(tmp)s(%(scope)s)"),
                        scope_args),),
                    finalize=True,
                    invert=True),
                 clauses.Else((
                     clauses.Write(types.template("%(tmp)s")),))
                 )))

            _.append(clauses.Else())

        # set dynamic content flag
        dynamic = content or self.translate is not None

        # if an attribute ordering is required, setting a default
        # trivial value for each attribute will ensure that the order
        # is preserved
        attributes = utils.odict()
        if self.attribute_ordering is not None:
            for name in self.attribute_ordering:
                attributes[name] = None

        # static attributes (including those with a namespace prefix)
        # are at the bottom of the food chain
        attributes.update(self.static_attributes)
        attributes.update(self.ns_attributes)

        # dynamic attributes
        dynamic_attrs = self.dynamic_attributes or ()
        dynamic_attr_names = []

        for variables, expression in dynamic_attrs:
            if len(variables) != 1:
                raise ValueError("Tuple definitions in assignment clause "
                                     "is not supported.")

            variable = variables[0]
            attributes[variable] = expression
            dynamic_attr_names.append(variable)

        # translated attributes
        translated_attributes = self.translated_attributes or ()
        for variable, msgid in translated_attributes:
            if msgid:
                if variable in dynamic_attr_names:
                    raise ValueError(
                        "Message id not allowed in conjunction with "
                        "a dynamic attribute.")

                value = types.value('"%s"' % msgid)

                if variable in attributes:
                    default = repr(attributes[variable])
                    expression = clauses.translate_expression(value, default=default)
                else:
                    expression = clauses.translate_expression(value)
            else:
                value = attributes.get(variable)
                if value is not None:
                    if variable not in dynamic_attr_names:
                        value = repr(value)
                    expression = clauses.translate_expression(value)
                else:
                    raise ValueError("Must be either static or dynamic "
                                     "attribute when no message id "
                                     "is supplied.")

            attributes[variable] = expression

        # tag
        text = self.text
        if omit is not True:
            selfclosing = not text and not dynamic and len(self.element) == 0
            tag = clauses.Tag(
                self.tag, attributes,
                expression=self.dict_attributes, selfclosing=selfclosing,
                cdata=self.cdata is not None, defaults=self.static_attributes)
            if omit:
                _.append(clauses.Condition(
                    omit, [tag], finalize=False, invert=True))
            else:
                _.append(tag)

        # tag text (if we're not replacing tag body)
        if len(text) and not dynamic and not self.use_macro and not self.extend_macro:
            for part in text:
                if isinstance(part, types.expression):
                    _.append(clauses.Write(part))
                else:
                    _.append(clauses.Out(part))

        # dynamic content
        if content:
            msgid = self.translate
            if msgid is not None:
                if msgid:
                    raise ValueError(
                        "Can't use message id with dynamic content translation.")

                _.append(clauses.Assign(content, self.symbols.tmp))
                content = clauses.translate_expression(
                    types.value(self.symbols.tmp))
            else:
                value = types.value(repr(utils.serialize(self.element, omit=True)))
                _.insert(0, clauses.Assign(
                    value, "%s.value = %s" % (
                        self.symbols.default_marker_symbol, self.symbols.default)))

            _.append(clauses.Write(content))

        # dynamic text
        elif self.translate is not None and \
                 True in map(lambda part: isinstance(part, types.expression), text):
            if len(self.element):
                raise ValueError(
                    "Can't translate dynamic text block with elements in it.")

            init_stream = types.value('_init_stream()')
            init_stream.symbol_mapping['_init_stream'] = generation.initialize_stream

            subclauses = []
            subclauses.append(clauses.Define(
                types.declaration((self.symbols.out, self.symbols.write)), init_stream))

            for part in text:
                if isinstance(part, types.expression):
                    subclauses.append(clauses.Write(part))
                else:
                    part = ' '.join(part.split())
                    if part != "":
                        subclauses.append(clauses.Out(part))

            # attempt translation
            subclauses.append(clauses.Assign(
                clauses.translate_expression(
                types.value('%(out)s.getvalue()'),
                default=None), self.symbols.tmp))

            _.append(clauses.Group(subclauses))
            _.append(clauses.Write(types.value(self.symbols.tmp)))

        # include
        elif self.include:
            # compute macro function arguments and create argument string
            arguments = [
                "%s=%s" % (arg, arg) for arg in \
                set(itertools.chain(*self.stream.scope[1:]))]

            # XInclude's are similar to METAL macros, except the macro
            # is always defined as the entire template.

            # first we compute the filename expression and write it to
            # an internal variable
            _.append(clauses.Assign(self.include, self.symbols.include))

            # call template
            _.append(clauses.Write(
                types.template(
                "%%(xincludes)s.get(%%(include)s, %s).render_xinclude(%s)" % \
                (repr(self.format), ", ".join(arguments)))))

        # use or extend macro
        elif self.use_macro or self.extend_macro:
            # assign macro value to variable
            macro = self.use_macro or self.extend_macro
            _.append(clauses.Assign(macro, self.symbols.metal))

            # for each fill-slot element, create a new output stream
            # and save value in a temporary variable
            kwargs = []
            callbacks = {}

            # determine variable scope
            scope = set(itertools.chain(adding, *self.stream.scope[1:])) - \
                    self.stream.scope[0]

            # we pass in all variables from the current scope (as
            # keyword arguments, to allow first use before potential
            # reassignment)
            callback_args = ", ".join(
                "%s=%s" % (arg, arg) for arg in scope
                if arg not in (self.symbols.slots, self.symbols.scope))

            macro_args = ", ".join(
                "%s=%s" % (arg, arg) for arg in scope
                if arg not in (self.symbols.slots,))

            # loop through macro fill slot elements and generate
            # callback methods; the reason why we use callbacks is
            # convenience: it's an easy fit with the compiler
            elements = [element for element in self.element.walk()
                        if element.node and element.node.fill_slot]

            for element in elements:
                # make sure we're not in a nested macro block
                parent = element.getparent()
                while parent is not self.element:
                    if parent.node.use_macro or parent.node.extend_macro:
                        element = None
                        break
                    parent = parent.getparent()

                if element is None:
                    continue

                # determine and register callback name
                name = element.node.fill_slot
                callbacks[name] = callback = "%s_%s" % (
                    self.symbols.callback, utils.normalize_slot_name(name))

                # pass in remote scope to callback method; this is
                # done because macros may add global variables to the
                # scope, which should be made available to the calling
                # template
                visitor = clauses.Visit(element.node)
                tail = element.tail
                newline = tail and '\n' in tail
                _.append(clauses.Callback(
                    callback, visitor, callback_args, newline))

            # if we're extending the macro, the current slots will be
            # carried over to the macro
            extend = self.extend_macro is not None
            defines = set()

            if extend:
                for element in self.element.walk():
                    if element.node is not None:
                        define_slot = element.node.define_slot
                        if define_slot is not None:
                            defines.add(define_slot)

            # format slot arguments
            slot_args = ", ".join("'%s': %s" % kwarg for kwarg in callbacks.items())

            _.append(clauses.Macro(
                types.value("{%s}" % slot_args),
                macro_args,
                extend=extend,
                extend_except=defines,
                label=macro.label
                ))

        # translate body
        elif self.translate is not None:
            msgid = self.translate

            # subelements are either named or unnamed; if there are
            # unnamed elements, the message id must be dynamic
            named_elements = [e for e in self.element
                              if e.node.translation_name]

            unnamed_elements = [e for e in self.element
                                if not e.node.translation_name]

            if unnamed_elements and msgid:
                elements = ()
            else:
                elements = tuple(self.element)

            # if no message id is provided, there are two cases:
            #
            # 1) all dynamic content is assigned a translation name
            # 2) the message id needs to be generated dynamically
            #
            if not msgid and not unnamed_elements:
                msgid = self.create_msgid()

            if named_elements:
                mapping = "%s_%d" % (self.symbols.mapping, id(self.element))
                _.append(clauses.Assign(types.value('{}'), mapping))
            else:
                mapping = 'None'

            if not msgid:
                text = utils.htmlescape(self.element.text.replace('%', '%%') or "")
                _.append(clauses.Assign(types.value(repr(text)),
                                        self.symbols.msgid))

            # for each named block, create a new output stream
            # and use the value in the translation mapping dict
            for element in elements:
                init_stream = types.value('_init_stream()')
                init_stream.symbol_mapping[
                    '_init_stream'] = generation.initialize_stream

                subclauses = []
                subclauses.append(clauses.Define(
                    types.declaration((self.symbols.out, self.symbols.write)), init_stream))
                subclauses.append(clauses.Visit(element.node))

                # if the element is named, record it in the mapping
                if element in named_elements:
                    name = element.node.translation_name

                    subclauses.append(clauses.Assign(
                        types.template('%(out)s.getvalue()'),
                        "%s['%s']" % (mapping, name)))

                    # when computing a dynamic message id, add a
                    # reference to the named block
                    if not msgid:
                        if not unnamed_elements:
                            subclauses.append(clauses.Assign(
                                types.value(repr("${%s}" % name)), self.symbols.msgid))
                        else:
                            subclauses.append(clauses.Assign(
                                types.template('%(msgid)s + ' + repr("${%s}" % name) + ' + ' + repr(element.tail)),
                                self.symbols.msgid))

                # else add it to the dynamic message id
                else:
                    subclauses.append(clauses.Assign(
                        types.template('%(msgid)s + %(out)s.getvalue()'),
                        self.symbols.msgid))

                # XXX: note that this should read:
                # _.append(clauses.Group(subclauses))
                #
                # but there's a problem with multiple temporary
                # variable assignments within the same block; this is
                # just an easy work-around
                _.append(clauses.Condition(
                    types.value('True'), subclauses, finalize=True))

            if msgid:
                value = types.value(repr(msgid)).replace('%', '%%')
                if elements:
                    default = self.symbols.marker
                else:
                    default = types.value(repr(
                        utils.serialize(self.element, omit=True))).replace('%', '%%')
            else:
                default = types.template('%(msgid)s')
                value = types.template("' '.join(%(msgid)s.split())")

            _.append(clauses.Assign(
                clauses.translate_expression(
                    value, mapping=mapping, default=default), self.symbols.result))

            # write translation to output if successful, otherwise
            # fallback to default rendition; 
            result = types.value(self.symbols.result)
            result.symbol_mapping[self.symbols.marker] = i18n.marker

            if msgid and elements:
                condition = types.template('%(result)s is not %(marker)s')
                _.append(clauses.Condition(
                    condition, [clauses.UnicodeWrite(result)], finalize=True))

                subclauses = []
                if self.element.text:
                    subclauses.append(clauses.Out(
                        utils.htmlescape(self.element.text)))
                for element in self.element:
                    name = element.node.translation_name
                    if name:
                        value = types.value("%s['%s']" % (mapping, name))
                        subclauses.append(clauses.Write(value))
                    else:
                        subclauses.append(clauses.Out(utils.serialize(element)))

                    for part in reversed(element.node.tail):
                        if isinstance(part, types.expression):
                            subclauses.append(clauses.Write(part))
                        else:
                            subclauses.append(clauses.Out(
                                utils.htmlescape(part)))

                if subclauses:
                    _.append(clauses.Else(subclauses))
            else:
                _.append(clauses.UnicodeWrite(result))

        return _

    def wrap_literal(self, element):
        index = self.element.index(element)

        t = self.element.makeelement(utils.meta_attr('literal'))
        t.meta_omit = ""
        t.tail = element.tail
        t.text = unicode(element)
        for child in element.getchildren():
            t.append(child)
        self.element.remove(element)
        self.element.insert(index, t)
        t.update()

    def create_msgid(self):
        """Create an i18n msgid from the tag contents."""

        out = StringIO()
        out.write(self.element.text)

        for element in self.element:
            name = element.node.translation_name
            assert name is not None

            out.write("${%s}" % name)
            out.write(element.tail)

        msgid = out.getvalue().strip()
        msgid = ' '.join(msgid.split())

        return msgid

class Element(etree.ElementBase):
    """Template element class.

    To start translation at this element, use the ``start`` method,
    providing a code stream object.
    """

    translator = None

    class node(Node):
        @property
        def omit(self):
            if self.element.meta_omit is not None:
                return self.element.meta_omit or True
            if self.element.meta_replace:
                return True

        @property
        def content(self):
            return self.element.meta_replace

    node = property(node)

    def start(self, stream):
        self._stream = stream
        self.node.visit()

    def update(self):
        pass

    @property
    def root(self):
        tree = self.getroottree()
        root = tree.getroot()

        while root is not None:
            parent = root.getparent()
            if parent is None:
                break
            root = parent

        return root

    @property
    def stream(self):
        try:
            return self.root._stream
        except AttributeError:
            raise AttributeError("Can't locate stream object.")

    meta_cdata = etree.Annotation(
        utils.meta_attr('cdata'))

    meta_omit = etree.Annotation(
        utils.meta_attr('omit-tag'))

    meta_omit_default_prefix = etree.Annotation(
        utils.meta_attr('omit-default-prefix'))

    meta_structure = etree.Annotation(
        utils.meta_attr('structure'))

    meta_attributes = etree.Annotation(
        utils.meta_attr('attributes'))

    meta_replace = etree.Annotation(
        utils.meta_attr('replace'))

class MetaElement(Element):
    meta_cdata = etree.Annotation('cdata')

    meta_omit = True

    meta_structure = True

    meta_attributes = etree.Annotation('attributes')

    meta_replace = etree.Annotation('replace')

    meta_omit_default_prefix = etree.Annotation('omit-default-prefix')

class Compiler(object):
    """Template compiler.

    Initializes a template compiler for a template expressed as an
    ElementTree-document (``tree``).

    Document type may be configured using ``implicit_doctype`` will be
    used as the document type if the template does not define one
    itself, while ``explicit_doctype`` may be used to explicitly set a
    doctype regardless of what the template defines.

    The ``encoding`` parameter may be provided to return a document in
    a non-unicode encoding.

    By default, native attributes are printed with no prefix. This
    behavior may be overriden using the ``omit_default_prefix``
    parameter (certain legacy applications such as OpenOffice require
    this formatting).
    """

    doctype = None

    def __init__(self, tree, explicit_doctype=None,
                 xml_declaration=None, encoding=None, omit_default_prefix=True):
        self.xml_declaration = xml_declaration
        self.omit_default_prefix = omit_default_prefix
        self.tree = tree

        # explicit document type has priority over a parsed doctype
        if explicit_doctype is not None:
            self.doctype = explicit_doctype
        elif tree.docinfo.doctype:
            self.doctype = tree.docinfo.doctype

        if utils.coerces_gracefully(encoding):
            self.encoding = None
        else:
            self.encoding = encoding

        macros = self.macros = {}

        for element in tree.getroot().walk():
            node = element.node
            if node is not None and node.define_macro is not None:
                define = element.node.define_macro
                extend = element.node.extend_macro

                # collect slot names
                names = set()

                for subelement in element.walk():
                    node = subelement.node
                    if node is not None and node.define_slot is not None:
                        names.add(node.define_slot)

                macros[define] = (extend is not None, names)

    def __call__(self, macro, global_scope=True, debug=False):
        root = copy.deepcopy(self.tree).getroot()

        if not isinstance(root, Element):
            raise ValueError(
                "Must define valid namespace for tag: '%s.'" % root.tag)

        # if macro is non-trivial, start compilation at the element
        # where the macro is defined
        if macro:
            for element in root.walk():
                node = element.node
                if node is not None and node.define_macro == macro:
                    element.meta_translator = root.meta_translator

                    # if element is the document root, render as a normal
                    # template, e.g. unset the `macro` mode
                    if root is element:
                        macro = None
                    else:
                        root = element

                    break
            else:
                raise KeyError(macro)

        # initialize code stream object
        stream = generation.CodeIO(
            root.node.symbols, encoding=self.encoding,
            indentation=0, indentation_string="\t")

        # transient symbols are added to the primary scope to exclude
        # them from being carried over when using macros
        for name, value in stream.symbols.as_dict().items():
            if value is config.TRANSIENT_SYMBOL:
                stream.scope[0].add(name)

        # initialize variable scope
        stream.scope.append(set(
            (stream.symbols.out,
             stream.symbols.write,
             stream.symbols.scope,
             stream.symbols.domain,
             stream.symbols.language)))

        if global_scope is False:
            stream.scope[-1].add(stream.symbols.remote_scope)

        # set up initialization code
        stream.symbol_mapping['_init_stream'] = generation.initialize_stream
        stream.symbol_mapping['_init_scope'] = generation.initialize_scope
        stream.symbol_mapping['_init_tal'] = generation.initialize_tal
        stream.symbol_mapping['_init_default'] = generation.initialize_default

        # add code-generation lookup globals
        if debug:
            lookup = codegen.lookup_attr_debug
        else:
            lookup = codegen.lookup_attr
        stream.symbol_mapping['_lookup_attr'] = lookup

        if global_scope:
            assignments = (
                clauses.Assign(
                    types.value("_init_stream()"), ("%(out)s", "%(write)s")),
                clauses.Assign(
                     types.value("_init_tal()"), ("%(attributes)s", "%(repeat)s")),
                clauses.Assign(
                    types.value("_init_default()"), '%(default_marker_symbol)s'),
                clauses.Assign(
                    types.value(repr(None)), '%(default)s'),
                clauses.Assign(
                     types.template("None"), "%(domain)s"))
        else:
            assignments = (
                clauses.Assign(
                    types.template(
                        "%(scope)s['%(out)s'], %(scope)s['%(write)s']"),
                    ("%(out)s", "%(write)s")),
                clauses.Assign(
                    types.value("_init_tal()"), ("%(attributes)s", "%(repeat)s")),
                clauses.Assign(
                    types.value("_init_default()"), '%(default_marker_symbol)s'),
                clauses.Assign(
                    types.value(repr(None)), '%(default)s'),
                clauses.Assign(
                     types.template("None"), "%(domain)s"))

        for clause in assignments:
            clause.begin(stream)
            clause.end(stream)

        if macro is not None:
            nsmap = {}
            namespaces = set()

            for tag in root.attrib:
                if '}' not in tag:
                    continue

                namespace = tag[1:].split('}')[0]
                namespaces.add(namespace)

            for prefix, namespace in root.nsmap.items():
                if namespace in namespaces:
                    nsmap[prefix] = namespace

            wrapper = self.tree.parser.makeelement(
                utils.meta_attr('wrapper'), root.attrib.copy(), nsmap=nsmap)
            wrapper.append(root)
            root = wrapper

        # output XML headers, if applicable
        if global_scope is True or macro is "":
            header = ""
            if self.xml_declaration is not None:
                header += self.xml_declaration + '\n'
            if self.doctype:
                doctype = self.doctype + '\n'
                if self.encoding:
                    doctype = doctype.encode(self.encoding)
                header += doctype
            if header:
                out = clauses.Out(header)
                stream.scope.append(set())
                stream.begin([out])
                stream.end([out])
                stream.scope.pop()

        # add meta settings
        root.meta_omit_default_prefix = self.omit_default_prefix

        # start generation
        root.start(stream)
        body = stream.getvalue()

        # symbols dictionary
        __dict__ = stream.symbols.as_dict()

        # prepare globals
        _globals = ["from cPickle import loads as _loads"]
        for symbol, value in stream.symbol_mapping.items():
            _globals.append(
                "%s = _loads(%s)" % (symbol, repr(dumps(value))))

        transient = []
        for name, value in stream.symbols.as_dict().items():
            if value is config.TRANSIENT_SYMBOL:
                transient.append("%s = econtext.get('%s')" % (name, name))
        transient = "; ".join(transient)

        # wrap generated Python-code in function definition
        if global_scope:
            source = generation.function_wrap(
                'render', _globals, body, transient,
                "%(out)s.getvalue()" % __dict__)
        else:
            source = generation.function_wrap(
                'render', _globals, body, transient)

        suite = codegen.Suite(source)
        return suite.source
