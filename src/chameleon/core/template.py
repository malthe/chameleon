import os
import sys
import doctypes
import tempfile
import utils
import i18n
import config
import filecache
import translation

try:
    from hashlib import sha1 as sha
except ImportError:
    from sha import sha

class Template(object):
    """Base template class.

    Note: template language implementations will usually make a
    subclass available for convenience.

    A language parser must be provided as ``parser``. The template
    ``body`` parameter must be a string.

    Most language parsers support two modes of operation: XML and text
    mode. This can be configured using the ``format`` parameter
    (provide either 'text' or 'xml').

    The default string type is unicode. Pass a value for ``encoding``
    if you need to allow strings that are not unicode or plain
    ASCII. Note that the output will always be unicode.

    To enable default attribute prefix rendering, use the
    ``omit_default_prefix`` parameter (required for certain legacy
    applications).

    To provide a custom translation function, use the ``translate``
    parameter.
    """

    format = 'xml'
    filename = '<string>'
    version = 8
    registry = None
    explicit_doctype = None
    encoding = None
    translate = staticmethod(i18n.fast_translate)

    def __init__(self, body, parser, format=None, doctype=None,
                 encoding=None, omit_default_prefix=True, translate=None):
        if encoding is not None:
            self.encoding = encoding

        if self.registry is None:
            # in debug-mode we initialize a filecache to a named
            # temporary file; this makes step-debugging through
            # generated template code possible
            if config.DEBUG_MODE:
                self.registry = filecache.TemplateCache(
                    tempfile.NamedTemporaryFile('w').name, 0)
            else:
                self.registry = filecache.TemplateRegistry()

        if format is not None:
            self.format = format

        if doctype is not None:
            self.explicit_doctype = doctype

        if translate is not None:
            self.translate = translate

        self.parser = parser
        self.body = body
        self.omit_default_prefix = omit_default_prefix
        self.signature = sha(";".join(map(str, (
            type(parser).__name__, format,
            encoding, omit_default_prefix,
            self.explicit_doctype)))).hexdigest()

    def compiler(self, *args):
        self.parse()
        return self.__dict__['compiler'](*args)

    def __repr__(self):
        return u"<%s %s>" % (self.__class__.__name__, self.filename)

    def __call__(self, **kwargs):
        return self.render(**kwargs)

    def write(self, body):
        self.__dict__['body'] = body
        self.__dict__.pop('compiler', None)
        if config.EAGER_PARSING:
            self.parse()

    def parse(self):
        body = self.__dict__['body']

        # if the body is trivial, we don't try to compile it
        if None in (body, self.parser):
            return

        parse_method = getattr(self.parser, 'parse_%s' % self.format)

        try:
            tree = parse_method(body)
        except:
            utils.raise_template_exception(
                repr(self), {}, sys.exc_info())

        # it's not clear from the tree if an XML declaration was
        # present in the document source; the following is a
        # work-around to ensure that output matches input
        if '<?xml ' in body:
            xml_declaration = \
            """<?xml version="%s" encoding="%s" standalone="no" ?>""" % (
                tree.docinfo.xml_version, tree.docinfo.encoding)
        else:
            xml_declaration = None

        explicit_doctype = self.explicit_doctype
        if not explicit_doctype is doctypes.no_doctype and not explicit_doctype:
            explicit_doctype = self.parser.doctype

        compiler = translation.Compiler(
            tree, explicit_doctype=explicit_doctype,
            xml_declaration=xml_declaration, encoding=self.encoding,
            omit_default_prefix=self.omit_default_prefix)

        self.__dict__['compiler'] = compiler
        self.__dict__['slots']  = compiler.macros
        self.__dict__['macros'] = Macros(self.render_macro, *compiler.macros)

    @property
    def macros(self):
        try:
            return self.__dict__['macros']
        except KeyError:
            self.parse()
            return self.__dict__['macros']

    @property
    def slots(self):
        try:
            return self.__dict__['slots']
        except KeyError:
            self.parse()
            return self.__dict__['slots']

    body = property(lambda template: template.__dict__['body'], write)

    def cook_and_render(self, kwargs, slots, macro, global_scope):
        """Cook and render template.

        This method finds a render-method from the template registry
        facility, cooking one if required (by invoking the compiler).
        """

        if self.compiler is None:
            raise NotImplemented("Python compiler-support required.")

        key = macro, global_scope, self.signature
        if key not in self.registry:
            source = self.compiler(macro, global_scope)
            self.registry.add(key, source)
            if key not in self.registry:
                raise RuntimeError(
                    "Unable to add template '%s' to registry (%s)." % (
                        self.filename, type(self.registry).__name__))

        func = self.registry[key]

        econtext = rcontext = kwargs.pop("econtext", self)
        if global_scope is False:
            econtext = econtext.copy()
        if econtext is self:
            econtext = utils.econtext(kwargs)
        else:
            econtext.update(kwargs)
        econtext[config.SYMBOLS.slots] = slots
        econtext.setdefault(config.SYMBOLS.translate, self.translate)

        __traceback_info__ = (self,)
        if config.DEBUG_MODE is False:
            return func(econtext, rcontext)
        try:
            return func(econtext, rcontext)
        except:
            utils.raise_template_exception(
                repr(self), kwargs, sys.exc_info())

    def render(self, *args, **kwargs):
        if args:
            try:
                slots, = args
            except TypeError:
                raise TypeError(
                    "render() takes 1 or 2 non-keyword argument (%d given)" % \
                        len(args))
            return self.render_macro(
                "", slots=slots, parameters=kwargs)
        return self.cook_and_render(kwargs, utils.emptydict, None, True)

    def render_macro(self, macro, global_scope=False, slots={}, parameters={}):
        if config.STRICT_MODE and macro != '':
            extend, names = self.slots[macro]
            if extend is False:
                for name in slots:
                    if name not in names:
                        raise KeyError(name)

        return self.cook_and_render(parameters, slots, macro, global_scope)

    def render_xinclude(self, **kwargs):
        return self.render_macro("", parameters=kwargs)

class TemplateFile(Template):
    """Constructs a template object using the template language
    defined by ``parser``. Must be passed an absolute (or
    current-working-directory-relative) filename as ``filename``. If
    ``auto_reload`` is true, each time the template is rendered, it
    will be recompiled if it has been changed since the last
    rendering."""

    content_type = None
    global_registry = {}

    def __init__(self, filename, parser, format=None,  doctype=None,
                 encoding=None, auto_reload=config.DEBUG_MODE):
        if encoding is not None:
            self.encoding = encoding

        # compute absolute filename
        self.filename = filename = os.path.abspath(
            os.path.normpath(os.path.expanduser(filename)))

        # make sure file exists
        os.lstat(filename)

        # persist template registry on disk
        if config.DISK_CACHE:
            hierarchy = sorted(
                utils.class_hierarchy(type(self)), key=utils.dotted_name)
            versions = (base.__dict__.get('version') for base in hierarchy)
            version = ".".join(map(str, filter(None, versions)))
            self.registry = filecache.TemplateCache(filename, version)

        # initialize template
        Template.__init__(self, None, parser, format=format, doctype=doctype)

        # read template (note that if we're unable to read the file,
        # we set ``auto_reload`` to true)
        if self.read() is False:
            auto_reload = True

        self.auto_reload = auto_reload
        self.global_registry.setdefault(filename, self)
        self.xincludes = XIncludes(
            self.global_registry, os.path.dirname(filename), self.clone)

    def clone(self, filename, format=None):
        cls = type(self)
        return cls(
            filename, self.parser, format=format,
            doctype=self.explicit_doctype, auto_reload=self.auto_reload)

    def _get_filename(self):
        return getattr(self, '_filename', None)

    def _set_filename(self, filename):
        self._filename = filename
        self._v_last_read = False

    filename = property(_get_filename, _set_filename)

    def read(self):
        filename = self.filename
        mtime = self.mtime()

        __traceback_info__ = filename
        fd = open(filename, "rb")
        try:
            body = fd.read(utils.XML_PREFIX_MAX_LENGTH)
        except:
            fd.close()
            raise

        content_type = utils.sniff_type(body)
        if content_type == "text/xml":
            body += fd.read()
            fd.close()
        else:
            # For HTML, we really want the file read in text mode:
            fd.close()
            fd = open(filename)
            body = fd.read()
            fd.close()

            # Look for an encoding specification in the meta tag
            match = utils.re_meta.search(body)
            if match is not None:
                content_type, encoding = match.groups()
            else:
                content_type = None
                encoding = config.DEFAULT_ENCODING
            try:
                body = unicode(body, encoding).encode(config.DEFAULT_ENCODING)
            except UnicodeDecodeError:
                body = None

        if body is not None:
            self.body = body
            self.content_type = content_type
            self._v_last_read = mtime

        # purge registry if source file is newer
        if self.registry.mtime < mtime:
            self.registry.purge()

        return body is not None

    def cook_and_render(self, args, slots, macro, global_scope):
        if self.auto_reload and self._v_last_read != self.mtime():
            if self.read() is False:
                raise RuntimeError(
                    "Unable to read body (%s)." % self.filename)

        return super(TemplateFile, self).cook_and_render(
            args, slots, macro, global_scope)

    @property
    def macros(self):
        if self.auto_reload and self._v_last_read != self.mtime():
            if self.read() is False:
                raise RuntimeError(
                    "Unable to read body (%s)." % self.filename)
        return Template.macros.fget(self)

    @property
    def slots(self):
        if self.auto_reload and self._v_last_read != self.mtime():
            if self.read() is False:
                raise RuntimeError(
                    "Unable to read body (%s)." % self.filename)
        return Template.slots.fget(self)

    def render(self, *args, **kwargs):
        kwargs[config.SYMBOLS.xincludes] = self.xincludes
        return super(TemplateFile, self).render(*args, **kwargs)

    def mtime(self):
        try:
            return os.path.getmtime(self.filename)
        except (IOError, OSError):
            return 0

class XIncludes(object):
    """Dynamic XInclude registry providing a ``get``-method that will
    resolve a filename to a template instance. Format must be
    explicitly provided."""
    
    def __init__(self, registry, relpath, factory):
        self.registry = registry
        self.relpath = relpath
        self.factory = factory

    def get(self, filename, format):
        if not os.path.isabs(filename):
            filename = os.path.join(self.relpath, filename)        
        template = self.registry.get(filename)
        if template is not None:
            return template
        return self.factory(filename, format=format)

class Macro(object):
    def __init__(self, render):
        self.render = render

class Macros(object):
    def __init__(self, render_macro, *names, **kwargs):
        self.render = render_macro
        self.bound_parameters = kwargs
        self.names = names

    def __getitem__(self, name):
        if name and name not in self.names:
            raise KeyError(name)
        return self.get_macro(name)

    def get_macro(self, name):
        def render(slots, **kwargs):
            kwargs.update(self.bound_parameters)
            return self.render(name, slots=slots, parameters=kwargs)
        return Macro(render)

    def bind(self, **kwargs):
        return Macros(self.render, *self.names, **kwargs)
