import os
import re
import sys
import copy
import atexit
import hashlib
import shutil
import logging
import tempfile
import inspect

pkg_digest = hashlib.sha1(__name__.encode('utf-8'))

try:
    import pkg_resources
except ImportError:
    logging.info("Setuptools not installed. Unable to determine version.")
else:
    for path in sys.path:
        for distribution in pkg_resources.find_distributions(path):
            if distribution.has_version():
                version = distribution.version.encode('utf-8')
                pkg_digest.update(version)


from .compiler import Compiler
from .loader import ModuleLoader
from .loader import MemoryLoader
from .exc import TemplateError
from .exc import ExceptionFormatter
from .config import DEBUG_MODE
from .config import AUTO_RELOAD
from .config import EAGER_PARSING
from .config import CACHE_DIRECTORY
from .utils import DebuggingOutputStream
from .utils import Scope
from .utils import join
from .utils import mangle
from .utils import derive_formatted_exception
from .nodes import Module

try:
    byte_string = str
    str = unicode
    bytes = byte_string
except NameError:
    def byte_string(string):
        return string.encode('utf-8')

version = sys.version_info[:3]
if version < (3, 0, 0):
    from .py25 import raise_with_traceback
else:
    def raise_with_traceback(exc, tb):
        exc.__traceback__ = tb
        raise exc


XML_PREFIXES = [
    byte_string(prefix) for prefix in(
        "<?xml",                      # ascii, utf-8
        "\xef\xbb\xbf<?xml",          # utf-8 w/ byte order mark
        "\0<\0?\0x\0m\0l",            # utf-16 big endian
        "<\0?\0x\0m\0l\0",            # utf-16 little endian
        "\xfe\xff\0<\0?\0x\0m\0l",    # utf-16 big endian w/ byte order mark
        "\xff\xfe<\0?\0x\0m\0l\0",    # utf-16 little endian w/ byte order mark
        )
    ]

XML_PREFIX_MAX_LENGTH = max(map(len, XML_PREFIXES))

RE_META = re.compile(
    r'\s*<meta\s+http-equiv=["\']?Content-Type["\']?'
    r'\s+content=["\']?([^;]+);\s*charset=([^"\']+)["\']?\s*/?\s*>\s*',
    re.IGNORECASE
    )

RE_ENCODING = re.compile(
    r'encoding\s*=\s*(?:"|\')(?P<encoding>[\w\-]+)(?:"|\')'.encode('ascii'),
    re.IGNORECASE
    )

log = logging.getLogger('chameleon.template')


def _make_module_loader():
    if CACHE_DIRECTORY:
        path = CACHE_DIRECTORY
    else:
        path = tempfile.mkdtemp()

        @atexit.register
        def cleanup(path=path, shutil=shutil):
            shutil.rmtree(path)

    return ModuleLoader(path)


class BaseTemplate(object):
    """Template base class.

    Input must be unicode (or string on Python 3).
    """

    # This attribute is strictly informational in this template class
    # and is used in exception formatting. It may be set on
    # initialization using the optional ``filename`` keyword argument.
    filename = '<string>'

    _cooked = False

    if DEBUG_MODE or CACHE_DIRECTORY:
        loader = _make_module_loader()
    else:
        loader = MemoryLoader()

    if DEBUG_MODE:
        output_stream_factory = DebuggingOutputStream
    else:
        output_stream_factory = list

    debug = DEBUG_MODE

    # The ``builtins`` dictionary can be used by a template class to
    # add symbols which may not be redefined and which are (cheaply)
    # available in the template variable scope
    builtins = {}

    # The ``builtins`` dictionary is updated with this dictionary at
    # cook time. Note that it can be provided at class initialization
    # using the ``extra_builtins`` keyword argument.
    extra_builtins = {}

    # Expression engine must be provided by subclass
    engine = None

    def __init__(self, body, **config):
        self.__dict__.update(config)

        self.content_type = self.sniff_type(body)
        self.cook(body)

        if self.__dict__.get('debug') is True:
            self.loader = _make_module_loader()

    def __call__(self, **kwargs):
        return self.render(**kwargs)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.filename)

    @property
    def keep_body(self):
        # By default, we only save the template body if we're
        # in debugging mode (to save memory).
        return self.__dict__.get('keep_body', DEBUG_MODE)

    @property
    def keep_source(self):
        # By default, we only save the generated source code if we're
        # in debugging mode (to save memory).
        return self.__dict__.get('keep_source', DEBUG_MODE)

    def cook(self, body):
        digest = self._digest(body)
        builtins_dict = self.builtins.copy()
        builtins_dict.update(self.extra_builtins)
        names, builtins = zip(*builtins_dict.items())
        program = self._cook(body, digest, names)

        initialize = program['initialize']
        functions = initialize(*builtins)

        for name, function in functions.items():
            setattr(self, "_" + name, function)

        self._cooked = True

        if self.keep_body:
            self.body = body

    def cook_check(self):
        assert self._cooked

    def parse(self, body):
        raise NotImplementedError("Must be implemented by subclass.")

    def render(self, **__kw):
        econtext = Scope(__kw)
        rcontext = {}
        self.cook_check()
        stream = self.output_stream_factory()
        try:
            self._render(stream, econtext, rcontext)
        except:
            cls, exc, tb = sys.exc_info()
            errors = rcontext.get('__error__')
            if errors:
                try:
                    exc = copy.copy(exc)
                except TypeError:
                    name = type(exc).__name__
                    log.warn("Unable to copy exception of type '%s'." % name)
                else:
                    formatter = ExceptionFormatter(errors, econtext, rcontext)
                    exc = derive_formatted_exception(exc, cls, formatter)

                raise_with_traceback(exc, tb)

            raise

        return join(stream)

    def sniff_type(self, text):
        """Return 'text/xml' if text appears to be XML, otherwise
        return None.
        """
        if not isinstance(text, bytes):
            text = text.encode('ascii', 'ignore')

        for prefix in XML_PREFIXES:
            if text[:len(prefix)] == prefix:
                return "text/xml"

    def _get_module_name(self, digest):
        return "%s.py" % digest

    def _cook(self, body, digest, builtins):
        name = self._get_module_name(digest)
        cooked = self.loader.get(name)
        if cooked is None:
            try:
                source = self._make(body, builtins)
                if self.debug:
                    source = "# template: %s\n#\n%s" % (self.filename, source)
                if self.keep_source:
                    self.source = source
                cooked = self.loader.build(source, name)
            except TemplateError:
                exc = sys.exc_info()[1]
                exc.filename = self.filename
                raise
        elif self.keep_source:
            module = sys.modules.get(cooked.get('__name__'))
            if module is not None:
                self.source = inspect.getsource(module)
            else:
                self.source = None

        return cooked

    def _digest(self, body):
        class_name = type(self).__name__.encode('utf-8')
        sha = pkg_digest.copy()
        sha.update(body.encode('utf-8', 'ignore'))
        sha.update(class_name)
        return sha.hexdigest()

    def _compile(self, program, builtins):
        compiler = Compiler(self.engine, program, builtins)
        return compiler.code

    def _make(self, body, builtins):
        program = self.parse(body)
        module = Module("initialize", program)
        return self._compile(module, builtins)


class BaseTemplateFile(BaseTemplate):
    """File-based template base class.

    Relative path names are supported only when a template loader is
    provided as the ``loader`` parameter.
    """

    # The default encoding is only for file content since it is always
    # 8-bit input
    default_encoding = "utf-8"

    # Auto reload is not enabled by default because it's a significant
    # performance hit
    auto_reload = AUTO_RELOAD

    def __init__(self, filename, auto_reload=None, **config):
        # Normalize filename
        filename = os.path.abspath(
            os.path.normpath(os.path.expanduser(filename))
            )

        self.filename = filename

        # Override reload setting only if value is provided explicitly
        if auto_reload is not None:
            self.auto_reload = auto_reload

        self.__dict__.update(config)

        # This is only necessary if the ``debug`` flag was passed as a
        # keyword argument
        if config.get('debug') is True:
            self.loader = _make_module_loader()

        if EAGER_PARSING:
            self.cook_check()

    def cook_check(self):
        if self.auto_reload:
            mtime = self.mtime()

            if mtime != self._v_last_read:
                self._v_last_read = mtime
                self._cooked = False

        if self._cooked is False:
            body = self.read()
            self.cook(body)

    def detect_encoding(self, body):
        # look for an encoding specification in the meta tag
        try:
            body = body.decode('ascii', 'ignore')
        except UnicodeDecodeError:
            pass
        else:
            match = RE_META.search(body)
            if match is not None:
                return match.groups()

        return None, self.default_encoding

    def read_xml_encoding(self, body):
        if body.startswith('<?xml'.encode('ascii')):
            match = RE_ENCODING.search(body)
            if match is not None:
                return match.group('encoding').decode('ascii')

    def mtime(self):
        try:
            return os.path.getmtime(self.filename)
        except (IOError, OSError):
            return 0

    def read(self):
        fd = open(self.filename, "rb")
        try:
            body = fd.read(XML_PREFIX_MAX_LENGTH)
        except:
            fd.close()
            raise

        content_type = self.content_type = self.sniff_type(body)

        if content_type == "text/xml":
            body += fd.read()
            fd.close()
            encoding = self.read_xml_encoding(body) or self.default_encoding
            body = body.decode(encoding)
        else:
            body += fd.read()
            content_type, encoding = self.detect_encoding(body)

            # for HTML, we really want the file read in text mode:
            fd.close()
            fd = open(self.filename, 'rb')
            body = fd.read().decode(encoding or self.default_encoding)
            fd.close()

        return body

    def _get_module_name(self, digest):
        filename = os.path.basename(self.filename)
        mangled = mangle(filename)
        return "%s_%s.py" % (mangled, digest)

    def _get_filename(self):
        return self.__dict__.get('filename')

    def _set_filename(self, filename):
        self.__dict__['filename'] = filename
        self._v_last_read = None
        self._cooked = False

    filename = property(_get_filename, _set_filename)
