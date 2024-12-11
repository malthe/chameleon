from __future__ import annotations

import contextlib
import functools
import importlib.resources
import logging
import os
import posixpath
import py_compile
import shutil
import sys
import tempfile
import warnings
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec
from importlib.util import spec_from_loader
from threading import RLock
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from chameleon.utils import encode_string


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from collections.abc import Sequence
    from pathlib import Path
    from typing import Protocol
    from typing import TypeVar

    from .template import BaseTemplate

    _F = TypeVar('_F', bound=Callable[..., Any])
    _TemplateT = TypeVar('_TemplateT', bound='BaseTemplate')

    class _SupportsRmtree(Protocol):
        def rmtree(self, path: str, /) -> object: ...


lock = RLock()
acquire_lock = lock.acquire
release_lock = lock.release
del lock

log = logging.getLogger('chameleon.loader')


def cache(func: _F) -> _F:
    def load(self: Any, *args: Any, **kwargs: Any) -> Any:
        template = self.registry.get(args)
        if template is None:
            self.registry[args] = template = func(self, *args, **kwargs)
        return template
    return cast('_F', load)


@contextlib.contextmanager
def import_package_resource(name: str) -> Iterator[Path]:
    # FIXME: we should restrict ourselves to the Traversable protocol
    #        but for right now we assume that we always get a simple
    #        filesystem resource loader which returns pathlib.Path objects
    path: Path = importlib.resources.files(name)  # type: ignore[assignment]
    yield path
    if hasattr(path.root, 'close'):
        path.root.close()


class TemplateLoader:
    """Template loader class.

    To load templates using relative filenames, pass a sequence of
    paths (or a single path) as ``search_path``.

    To apply a default filename extension to inputs which do not have
    an extension already (i.e. no dot), provide this as
    ``default_extension`` (e.g. ``'.pt'``).

    Additional keyword-arguments will be passed on to the template
    constructor.
    """

    default_extension: str | None = None
    registry: dict[tuple[Any, ...], Any]

    def __init__(
        self,
        search_path: Sequence[str] | str | None = None,
        default_extension: str | None = None,
        **kwargs: Any
    ) -> None:

        if search_path is None:
            search_path = []
        if isinstance(search_path, str):
            search_path = [search_path]
        if default_extension is not None:
            self.default_extension = ".%s" % default_extension.lstrip('.')
        self.search_path = search_path
        self.registry = {}
        self.kwargs = kwargs

    @cache
    def load(
        self,
        spec: str,
        cls: type[_TemplateT] = None  # type: ignore[assignment]
    ) -> _TemplateT:

        if cls is None:
            raise ValueError("Unbound template loader.")

        spec = spec.strip()

        if self.default_extension is not None and '.' not in spec:
            spec += self.default_extension

        package_name = None

        if not os.path.isabs(spec):
            if ':' in spec:
                package_name, spec = spec.split(':', 1)
            else:
                for path in self.search_path:
                    if not os.path.isabs(path) and ':' in path:
                        package_name, path = path.split(':', 1)
                        with import_package_resource(package_name) as files:
                            if files.joinpath(path).joinpath(spec).exists():
                                spec = posixpath.join(path, spec)
                                break
                    else:
                        path = os.path.join(path, spec)
                        if os.path.exists(path):
                            package_name = None
                            spec = path
                            break
                else:
                    raise ValueError("Template not found: %s." % spec)

        return cls(
            spec,
            search_path=self.search_path,
            package_name=package_name,
            **self.kwargs
        )

    def bind(
        self,
        cls: type[_TemplateT]
    ) -> Callable[[str], _TemplateT]:
        return functools.partial(self.load, cls=cls)


class MemoryLoader:
    def build(self, source: str, filename: str) -> dict[str, Any]:
        code = compile(source, filename, 'exec')
        env: dict[str, Any] = {}
        exec(code, env)
        return env

    def get(self, name: str) -> None:
        return None


class ModuleLoader:
    def __init__(self, path: str, remove: bool = False) -> None:
        self.path = path
        self.remove = remove

    def __del__(self, shutil: _SupportsRmtree = shutil) -> None:
        if not self.remove:
            return
        try:
            shutil.rmtree(self.path)
        except BaseException:
            warnings.warn(
                "Could not clean up temporary file path: %s" % (self.path,)
            )

    def get(self, filename: str) -> dict[str, Any] | None:
        path = os.path.join(self.path, filename)
        if os.path.exists(path):
            log.debug("loading module from cache: %s." % filename)
            base, ext = os.path.splitext(filename)
            return self._load(base, path)
        else:
            log.debug('cache miss: %s' % filename)
            return None

    def build(self, source: str, filename: str) -> dict[str, Any]:
        acquire_lock()
        try:
            base, ext = os.path.splitext(filename)
            name = os.path.join(self.path, base + ".py")

            log.debug("writing source to disk (%d bytes)." % len(source))
            fd, fn = tempfile.mkstemp(
                prefix=base, suffix='.tmp', dir=self.path)
            temp = os.fdopen(fd, 'wb')
            encoded = source.encode('utf-8')
            header = encode_string("# -*- coding: utf-8 -*-" + "\n")

            try:
                try:
                    temp.write(header)
                    temp.write(encoded)
                finally:
                    temp.close()
            except BaseException:
                os.remove(fn)
                raise

            os.rename(fn, name)
            log.debug("compiling %s into byte-code..." % filename)
            py_compile.compile(name)

            return self._load(base, name)
        finally:
            release_lock()

    def _load(self, base: str, filename: str) -> dict[str, Any]:
        acquire_lock()
        try:
            module = sys.modules.get(base)
            if module is None:
                loader = SourceFileLoader(base, filename)
                spec = spec_from_loader(base, loader)
                if spec is None:
                    raise ModuleNotFoundError(f"{base} ({filename})")
                module = module_from_spec(spec)
                loader.exec_module(module)
                sys.modules[base] = module
        finally:
            release_lock()

        return module.__dict__
