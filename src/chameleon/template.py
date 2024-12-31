from __future__ import annotations

import datetime
import hashlib
import inspect
import logging
import os
import pathlib
import sys
import tempfile
from typing import TYPE_CHECKING
from typing import Any

from chameleon.compiler import Compiler
from chameleon.config import AUTO_RELOAD
from chameleon.config import CACHE_DIRECTORY
from chameleon.config import DEBUG_MODE
from chameleon.config import EAGER_PARSING
from chameleon.exc import ExceptionFormatter
from chameleon.exc import RenderError
from chameleon.exc import TemplateError
from chameleon.loader import MemoryLoader
from chameleon.loader import ModuleLoader
from chameleon.loader import import_package_resource
from chameleon.nodes import Module
from chameleon.utils import DebuggingOutputStream
from chameleon.utils import Scope
from chameleon.utils import create_formatted_exception
from chameleon.utils import detect_encoding
from chameleon.utils import join
from chameleon.utils import mangle
from chameleon.utils import raise_with_traceback
from chameleon.utils import read_bytes
from chameleon.utils import read_xml_encoding
from chameleon.utils import value_repr


PROGRAM_NAME = "initialize"


if TYPE_CHECKING:
    from _typeshed import StrPath
    from abc import abstractmethod
    from collections.abc import Callable
    from collections.abc import Collection

    from chameleon.compiler import ExpressionEngine


if sys.version_info >= (3, 10):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata


def safe_get_package_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def get_package_versions() -> list[tuple[str, str]]:
    distributions = importlib_metadata.packages_distributions().values()
    versions = {
        x: safe_get_package_version(x) or ""
        for x in sum(distributions, [])
    }
    return sorted(versions.items())


_pkg_digest = None


def get_pkg_digest() -> hashlib._Hash:
    global _pkg_digest
    if _pkg_digest is None:
        _pkg_digest = hashlib.sha1(__name__.encode('utf-8'))
        for name, version in get_package_versions():
            _pkg_digest.update(name.encode('utf-8'))
            _pkg_digest.update(version.encode('utf-8'))
    return _pkg_digest.copy()


log = logging.getLogger('chameleon.template')


def _make_module_loader() -> ModuleLoader:
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
    default_content_type: str | None = None

    # This attribute is strictly informational in this template class
    # and is used in exception formatting. It may be set on
    # initialization using the optional ``filename`` keyword argument.
    filename: StrPath = '<string>'

    _cooked = False

    loader: ModuleLoader | MemoryLoader
    if DEBUG_MODE or CACHE_DIRECTORY:
        loader = _make_module_loader()
    else:
        loader = MemoryLoader()

    output_stream_factory: type[list]
    if DEBUG_MODE:
        output_stream_factory = DebuggingOutputStream
    else:
        output_stream_factory = list

    debug = DEBUG_MODE

    # The ``builtins`` dictionary can be used by a template class to
    # add symbols which may not be redefined and which are (cheaply)
    # available in the template variable scope
    builtins: dict[str, Any] = {}

    # The ``builtins`` dictionary is updated with this dictionary at
    # cook time. Note that it can be provided at class initialization
    # using the ``extra_builtins`` keyword argument.
    extra_builtins: dict[str, Any] = {}

    # Expression engine must be provided by subclass
    if TYPE_CHECKING:
        @property
        @abstractmethod
        def engine(self) -> Callable[[], ExpressionEngine]: ...
    else:
        engine = None

    # When ``strict`` is set, expressions must be valid at compile
    # time. When not set, this is only required at evaluation time.
    strict = True

    # This should return a value string representation for exception
    # formatting.
    value_repr = staticmethod(value_repr)

    source: str | None

    def __init__(
        self,
        body: str | bytes | None = None,
        **config: Any
    ) -> None:

        self.__dict__.update(config)

        if body is not None:
            self.write(body)

        # This is only necessary if the ``debug`` flag was passed as a
        # keyword argument
        if self.__dict__.get('debug') is True:
            self.loader = _make_module_loader()

    def __call__(self, **kwargs: Any) -> str:
        return self.render(**kwargs)

    def __repr__(self) -> str:
        return "<{} {}>".format(self.__class__.__name__, self.filename)

    if TYPE_CHECKING:
        # since we add config values to our __dict__ they can appear as
        # arbitrary attributes, to clue the type checker into arbitary
        # attribute access being a possibility, we annotate __getattr__
        def __getattr__(self, name: str) -> Any: ...

    @property
    def keep_body(self) -> bool:
        # By default, we only save the template body if we're
        # in debugging mode (to save memory).
        return self.__dict__.get('keep_body', DEBUG_MODE)  # type: ignore

    @property
    def keep_source(self) -> bool:
        # By default, we only save the generated source code if we're
        # in debugging mode (to save memory).
        return self.__dict__.get('keep_source', DEBUG_MODE)  # type: ignore

    def cook(self, body: str) -> None:
        builtins_dict = self.builtins.copy()
        builtins_dict.update(self.extra_builtins)
        names, builtins = zip(*sorted(builtins_dict.items()))
        digest = self.digest(body, names)
        program = self._cook(body, digest, names)

        init = program[PROGRAM_NAME]
        functions = init(*builtins)

        for name, function in functions.items():
            setattr(self, "_" + name, function)

        self._cooked = True

        if self.keep_body:
            self.body = body

    def cook_check(self) -> bool | None:
        assert self._cooked
        return None

    def parse(self, body: str) -> Any:
        raise NotImplementedError("Must be implemented by subclass.")

    def render(self, **__kw: Any) -> str:
        econtext = Scope(__kw)
        rcontext: dict[str, Any] = {}
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
                            exc, cls, formatter, RenderError  # type: ignore
                        )
                    except TypeError:
                        pass

                    assert exc is not None
                    raise_with_traceback(exc, tb)

                raise
            finally:
                del exc, tb

        return join(stream)

    def write(self, body: str | bytes) -> None:
        encoding: str | None
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

    def _get_module_name(self, name: str) -> str:
        return "%s.py" % name

    def _cook(
        self,
        body: str,
        name: str,
        builtins: Collection[str]
    ) -> dict[str, Any]:

        filename = self._get_module_name(name)
        if DEBUG_MODE or (cooked := self.loader.get(filename)) is None:
            try:
                source = self._compile(body, builtins)
                if self.debug:
                    source = "# template: {}\n#\n{}".format(
                        self.filename, source)
                if self.keep_source:
                    self.source = source
                cooked = self.loader.build(source, filename)
            except TemplateError as exc:
                # normalize to str
                exc.token.filename = str(self.filename)
                raise
        elif self.keep_source:
            module_name = cooked.get('__name__')
            module = sys.modules.get(module_name) if module_name else None
            if module is not None:
                self.source = inspect.getsource(module)
            else:
                self.source = None
        return cooked

    def digest(self, body: str, names: Collection[str]) -> str:
        class_name = type(self).__name__.encode('utf-8')
        sha = get_pkg_digest()
        sha.update(body.encode('utf-8', 'ignore'))
        sha.update(class_name)
        digest = sha.hexdigest()

        filename = str(self.filename)
        if filename and filename != BaseTemplate.filename:
            digest = os.path.splitext(filename)[0] + '-' + digest

        return digest

    def _compile(self, body: str, builtins: Collection[str]) -> str:
        program = self.parse(body)
        module = Module(PROGRAM_NAME, program)
        compiler = Compiler(
            self.engine,
            module,
            str(self.filename),
            body,
            builtins=builtins,
            strict=self.strict
        )
        return compiler.code  # type: ignore[no-any-return]


class BaseTemplateFile(BaseTemplate):
    """File-based template base class.

    Relative path names are supported only when a template loader is
    provided as the ``loader`` parameter.
    """

    # Auto reload is not enabled by default because it's a significant
    # performance hit
    auto_reload = AUTO_RELOAD

    _v_last_read: float | None

    def __init__(
        self,
        filename: StrPath,
        auto_reload: bool | None = None,
        package_name: str | None = None,
        post_init_hook: Callable[[], object] | None = None,
        **config: Any,
    ) -> None:

        if package_name is None:
            # Normalize filename
            filename = os.path.abspath(
                os.path.normpath(os.path.expanduser(filename))
            )
        self.package_name = package_name
        self.filename = filename

        # Override reload setting only if value is provided explicitly
        if auto_reload is not None:
            self.auto_reload = auto_reload

        super().__init__(**config)

        if post_init_hook is not None:
            post_init_hook()

        if EAGER_PARSING:
            self.cook_check()

    def cook_check(self) -> bool:
        if self.auto_reload:
            mtime = self.mtime()

            if mtime != self._v_last_read:
                self._v_last_read = mtime
                self._cooked = False

        if self._cooked is False:
            body = self.read()
            log.debug("cooking %r (%d bytes)..." % (self.filename, len(body)))
            self.cook(body)
            return True

        return False

    def mtime(self) -> float:
        filename = self.filename
        if self.package_name is not None:
            with import_package_resource(self.package_name) as path:
                joined = path.joinpath(filename)
                if isinstance(joined, pathlib.Path):
                    return joined.stat().st_mtime

                # Assume this is a zip-like path object:
                filename = joined.at
                timetuple = path.root.getinfo(filename).date_time
                return datetime.datetime(*timetuple).timestamp()
        try:
            return os.path.getmtime(filename)
        except OSError:
            return 0

    def read(self) -> str:
        if self.package_name is not None:
            with import_package_resource(self.package_name) as files:
                path = files.joinpath(self.filename)
                data = path.read_bytes()
        else:
            with open(self.filename, "rb") as f:
                data = f.read()

        body, encoding, content_type = read_bytes(data, self.default_encoding)

        self.content_type = content_type or self.default_content_type
        self.content_encoding = encoding

        return body

    def _get_module_name(self, name: str) -> str:
        filename = os.path.basename(str(self.filename))
        mangled = mangle(filename)
        return "{}_{}.py".format(mangled, name)

    def _get_filename(self) -> StrPath:
        # FIXME: Shouldn't a missing filename be an error?
        return self.__dict__.get('filename')  # type: ignore[return-value]

    def _set_filename(self, filename: StrPath) -> None:
        self.__dict__['filename'] = filename
        self._v_last_read = None
        self._cooked = False

    if TYPE_CHECKING:
        # type checkers only understand this way of defining properties
        @property
        def filename(self) -> StrPath: ...
        @filename.setter
        def filename(self, filename: StrPath) -> None: ...
    else:
        filename = property(_get_filename, _set_filename)
