import os
import re
import sys
import atexit
import hashlib
import shutil
import logging
import tempfile

try:
    import pkg_resources
except ImportError:
    pkg_version = 0
else:
    try:
        distribution = pkg_resources.get_distribution("Chameleon")
    except pkg_resources.DistributionNotFound:
        pkg_version = ""
    else:
        if distribution.has_version():
            pkg_version = distribution.version
        else:
            pkg_version = ""

from .compiler import Compiler
from .loader import ModuleLoader
from .loader import MemoryLoader
from .exc import TemplateError
from .config import DEBUG_MODE
from .config import AUTO_RELOAD
from .config import EAGER_PARSING
from .config import CACHE_DIRECTORY
from .utils import DebuggingOutputStream
from .utils import Scope

try:
    byte_string = str
    str = unicode
    bytes = byte_string
except NameError:
    def byte_string(string):
        return string.encode('utf-8')


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

log = logging.getLogger('chameleon.template')


class BaseTemplate(object):
    """Template base class.

    Input must be unicode (or string on Python 3).
    """

    filename = '<string>'

    _cooked = False

    if DEBUG_MODE:
        if CACHE_DIRECTORY:
            path = CACHE_DIRECTORY
        else:
            path = tempfile.mkdtemp()

            @atexit.register
            def cleanup(path=path):
                shutil.rmtree(path)

        loader = ModuleLoader(path)
    else:
        loader = MemoryLoader()

    if DEBUG_MODE:
        output_stream_factory = DebuggingOutputStream
    else:
        output_stream_factory = list

    # Compatibility with 1.x API
    debug = DEBUG_MODE

    def __init__(self, body, **kwargs):
        self.__dict__.update(kwargs)

        self.content_type = self.sniff_type(body)
        self.cook(body)

    def __call__(self, **kwargs):
        return self.render(**kwargs)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.filename)

    @property
    def keep_source(self):
        # By default, we only save the generated source code if we're in debugging
        # mode (to save memory).
        return self.__dict__.get('keep_source', DEBUG_MODE)

    def cook(self, body):
        digest = self._digest(body)

        for name, function in self._cook(body, digest).items():
            if not name.startswith('render'):
                continue

            setattr(self, "_" + name, function)

        self._cooked = True

    def cook_check(self):
        assert self._cooked

    def parse(self, body):
        raise NotImplementedError("Must be implemented by subclass.")

    def render(self, **kwargs):
        stream = self.output_stream_factory()
        econtext = kwargs.pop('econtext', False) or Scope(kwargs)
        self.cook_check()
        self._render(stream, econtext, kwargs)
        return "".join(stream)

    def sniff_type(self, text):
        """Return 'text/xml' if text appears to be XML, otherwise
        return None.
        """
        if not isinstance(text, bytes):
            text = text.encode('ascii', 'ignore')

        for prefix in XML_PREFIXES:
            if text[:len(prefix)] == prefix:
                return "text/xml"

    def _cook(self, body, digest):
        program = self.parse(body)
        source = self._compile(program)

        if self.keep_source:
            self.source = source

        filename = "%s.py" % digest
        return self.loader.get(filename) or \
               self.loader.build(source, filename)

    def _digest(self, body):
        sha = hashlib.sha1(body.encode('utf-8'))
        sha.update(type(self).__name__.encode('utf-8'))
        sha.update(pkg_version.encode('utf-8'))
        return sha.hexdigest()

    def _compile(self, program):
        compiler = Compiler(self.engine, program)
        return compiler.code


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
    auto_reload = False

    def __init__(self, filename, *args, **kwargs):
        if not os.path.isabs(filename):
            try:
                loader = kwargs['loader']
            except KeyError:
                raise KeyError(
                    "Must provide template loader for "
                    "relative filenames ('%s')." % filename)

            filename = loader.find(filename)

        self.filename = filename
        self.auto_reload = kwargs.pop('auto_reload', AUTO_RELOAD)

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
            body = body.decode('utf-8')
        else:
            body += fd.read()
            content_type, encoding = self.detect_encoding(body)

            # for HTML, we really want the file read in text mode:
            fd.close()
            fd = open(self.filename, 'rb')
            body = fd.read().decode(encoding or self.default_encoding)
            fd.close()

        return body

    def _get_filename(self):
        return self.__dict__.get('filename')

    def _set_filename(self, filename):
        self.__dict__['filename'] = filename
        self._v_last_read = None

    filename = property(_get_filename, _set_filename)

    body = property(read)

    def _cook(self, body, digest):
        filename = os.path.basename(self.filename)
        base, ext = os.path.splitext(filename)
        name = "%s_%s.py" % (base, digest)
        cooked = self.loader.get(name)

        if cooked is None:
            log.debug('cache miss: %s' % self.filename)
            try:
                nodes = self.parse(body)
                source = self._compile(nodes)

                if DEBUG_MODE:
                    source = "# filename: %s\n#\n%s" % (self.filename, source)

                cooked = self.loader.build(source, name)
            except TemplateError:
                exc = sys.exc_info()[1]
                exc.filename = self.filename
                raise
        else:
            log.debug('cache hit: %s' % self.filename)

        return cooked
