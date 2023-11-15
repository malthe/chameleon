import hashlib
import inspect
import logging
import os
import sys
import tempfile
import warnings


try:
    # we need to try the backport first, as we rely on ``files`` added in 3.9
    import importlib_resources
except ImportError:
    import importlib.resources as importlib_resources

from .compiler import Compiler
from .config import AUTO_RELOAD
from .config import CACHE_DIRECTORY
from .config import DEBUG_MODE
from .config import EAGER_PARSING
from .exc import ExceptionFormatter
from .exc import RenderError
from .exc import TemplateError
from .loader import MemoryLoader
from .loader import ModuleLoader
from .nodes import Module
from .utils import DebuggingOutputStream
from .utils import Scope
from .utils import create_formatted_exception
from .utils import detect_encoding
from .utils import join
from .utils import mangle
from .utils import raise_with_traceback
from .utils import read_bytes
from .utils import read_xml_encoding
from .utils import value_repr


try:
    RecursionError
except NameError:
    RecursionError = RuntimeError


def get_package_versions():
    try:
        # try backport first as packages_distributions was added in Python 3.10
        import importlib_metadata
    except ImportError:
        import importlib.metadata as importlib_metadata

    versions = {
        x: importlib_metadata.version(x)
        for x in sum(importlib_metadata.packages_distributions().values(), [])}
    return sorted(versions.items())


pkg_digest = hashlib.sha1(__name__.encode('utf-8'))
for name, version in get_package_versions():
    pkg_digest.update(name.encode('utf-8'))
    pkg_digest.update(version.encode('utf-8'))


log = logging.getLogger('chameleon.template')


def _make_module_loader():
    remove = False
    if CACHE_DIRECTORY:
        path = CACHE_DIRECTORY
    else:
        path = tempfile.mkdtemp()
        remove = True

    return ModuleLoader(path, remove)


class BaseTemplate:
    """Template base class.

    Takes a string input which must be one of the following:

    - a string;
    - a utf-8 encoded byte string;
    - a byte string for an XML document that defines an encoding
      in the document premamble;
    - an HTML document that specifies the encoding via the META tag.

    Note that the template input is decoded, parsed and compiled on
    initialization.
    """

    default_encoding = "utf-8"
    default_content_type = None

    # This attribute is strictly informational in this template class
    # and is used in exception formatting. It may be set on
    # initialization using the optional ``spec`` keyword argument.
    spec = '<string>'

    @property
    def filename(self):
        warnings.warn(
            "The filename attribute is deprecated, use spec instead.",
            DeprecationWarning,
            stacklevel=2)
        return self.spec

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

    # When ``strict`` is set, expressions must be valid at compile
    # time. When not set, this is only required at evaluation time.
    strict = True

    # This should return a value string representation for exception
    # formatting.
    value_repr = staticmethod(value_repr)

    def __init__(self, body=None, **config):
        self.__dict__.update(config)

        if body is not None:
            self.write(body)

        # This is only necessary if the ``debug`` flag was passed as a
        # keyword argument
        if self.__dict__.get('debug') is True:
            self.loader = _make_module_loader()

    def __call__(self, **kwargs):
        return self.render(**kwargs)

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, self.spec)

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
        builtins_dict = self.builtins.copy()
        builtins_dict.update(self.extra_builtins)
        names, builtins = zip(*sorted(builtins_dict.items()))
        digest = self.digest(body, names)
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
        target_language = __kw.get("target_language")
        try:
            self._render(
                stream,
                econtext,
                rcontext,
                target_language=target_language
            )
        except RecursionError:
            raise
        except BaseException:
            cls, exc, tb = sys.exc_info()
            try:
                errors = rcontext.get('__error__')
                if errors:
                    formatter = exc.__str__
                    if isinstance(formatter, ExceptionFormatter):
                        if errors is not formatter._errors:
                            formatter._errors.extend(errors)
                        raise

                    formatter = ExceptionFormatter(
                        errors, econtext, rcontext, self.value_repr)

                    try:
                        exc = create_formatted_exception(
                            exc, cls, formatter, RenderError
                        )
                    except TypeError:
                        pass

                    raise_with_traceback(exc, tb)

                raise
            finally:
                del exc, tb

        return join(stream)

    def write(self, body):
        if isinstance(body, bytes):
            body, encoding, content_type = read_bytes(
                body, self.default_encoding
            )
        elif body.startswith('<?xml'):
            content_type = 'text/xml'
            encoding = read_xml_encoding(body.encode("utf-8"))
        else:
            content_type, encoding = detect_encoding(
                body, self.default_encoding
            )

        self.content_type = content_type or self.default_content_type
        self.content_encoding = encoding

        self.cook(body)

    def _get_module_name(self, name):
        return "%s.py" % name

    def _cook(self, body, name, builtins):
        filename = self._get_module_name(name)
        cooked = self.loader.get(filename)
        if cooked is None:
            try:
                source = self._compile(body, builtins)
                if self.debug:
                    source = "# template: {}\n#\n{}".format(
                        self.spec, source)
                if self.keep_source:
                    self.source = source
                cooked = self.loader.build(source, filename)
            except TemplateError as exc:
                exc.token.filename = self.spec
                raise
        elif self.keep_source:
            module = sys.modules.get(cooked.get('__name__'))
            if module is not None:
                self.source = inspect.getsource(module)
            else:
                self.source = None
        return cooked

    def digest(self, body, names):
        class_name = type(self).__name__.encode('utf-8')
        sha = pkg_digest.copy()
        sha.update(body.encode('utf-8', 'ignore'))
        sha.update(class_name)
        digest = sha.hexdigest()

        if self.spec and self.spec is not BaseTemplate.spec:
            digest = os.path.splitext(self.spec.filename)[0] + '-' + digest

        return digest

    def _compile(self, body, builtins):
        program = self.parse(body)
        module = Module("initialize", program)
        compiler = Compiler(
            self.engine, module, self.spec, body,
            builtins, strict=self.strict
        )
        return compiler.code


class Spec(object):
    __slots__ = ('filename', 'pname', 'spec')

    def __init__(self, spec):
        self.spec = spec
        if ':' in spec:
            (self.pname, self.filename) = spec.split(':', 1)
        else:
            self.pname = None
            self.filename = spec

    def __repr__(self):
        return repr(self.spec)


class BaseTemplateFile(BaseTemplate):
    """File-based template base class.

    Relative path names are supported only when a template loader is
    provided as the ``loader`` parameter.
    """

    # Auto reload is not enabled by default because it's a significant
    # performance hit
    auto_reload = AUTO_RELOAD

    def __init__(
            self,
            spec,
            auto_reload=None,
            post_init_hook=None,
            **config):
        if ':' not in spec:
            # Normalize filename
            spec = os.path.abspath(
                os.path.normpath(os.path.expanduser(spec))
            )

        self.spec = Spec(spec)

        # Override reload setting only if value is provided explicitly
        if auto_reload is not None:
            self.auto_reload = auto_reload

        super().__init__(**config)

        if post_init_hook is not None:
            post_init_hook()

        if EAGER_PARSING:
            self.cook_check()

    @property
    def filename(self):
        warnings.warn(
            "The filename attribute is deprecated, use spec.filename instead.",
            DeprecationWarning,
            stacklevel=2)
        return self.spec.filename

    def cook_check(self):
        if self.auto_reload:
            mtime = self.mtime()

            if mtime != self._v_last_read:
                self._v_last_read = mtime
                self._cooked = False

        if self._cooked is False:
            body = self.read()
            log.debug("cooking %r (%d bytes)..." % (self.spec, len(body)))
            self.cook(body)

    def mtime(self):
        if self.spec.pname is not None:
            return 0
        else:
            try:
                return os.path.getmtime(self.spec.filename)
            except OSError:
                return 0

    def read(self):
        if self.spec.pname is not None:
            files = importlib_resources.files(self.spec.pname)
            data = files.joinpath(self.spec.filename).read_bytes()
        else:
            with open(self.spec.filename, "rb") as f:
                data = f.read()

        body, encoding, content_type = read_bytes(
            data, self.default_encoding
        )

        self.content_type = content_type or self.default_content_type
        self.content_encoding = encoding

        return body

    def _get_module_name(self, name):
        filename = os.path.basename(self.spec.filename)
        mangled = mangle(filename)
        return "{}_{}.py".format(mangled, name)

    def _get_spec(self):
        return self.__dict__.get('spec')

    def _set_spec(self, spec):
        self.__dict__['spec'] = spec
        self._v_last_read = None
        self._cooked = False

    spec = property(_get_spec, _set_spec)
