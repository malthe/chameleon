import functools
import imp
import logging
import os
import py_compile
import shutil
import sys
import tempfile
import warnings
import pkg_resources

log = logging.getLogger('chameleon.loader')

from .utils import string_type
from .utils import encode_string


def cache(func):
    def load(self, *args, **kwargs):
        template = self.registry.get(args)
        if template is None:
            self.registry[args] = template = func(self, *args, **kwargs)
        return template
    return load


def abspath_from_asset_spec(spec):
    pname, filename = spec.split(':', 1)
    return pkg_resources.resource_filename(pname, filename)

if os.name == "nt":
    def abspath_from_asset_spec(spec, f=abspath_from_asset_spec):
        if spec[1] == ":":
            return spec
        return f(spec)


class TemplateLoader(object):
    """Template loader class.

    To load templates using relative filenames, pass a sequence of
    paths (or a single path) as ``search_path``.

    To apply a default filename extension to inputs which do not have
    an extension already (i.e. no dot), provide this as
    ``default_extension`` (e.g. ``'.pt'``).

    Additional keyword-arguments will be passed on to the template
    constructor.
    """

    default_extension = None

    def __init__(self, search_path=None, default_extension=None, **kwargs):
        if search_path is None:
            search_path = []
        if isinstance(search_path, string_type):
            search_path = [search_path]
        if default_extension is not None:
            self.default_extension = ".%s" % default_extension.lstrip('.')
        self.search_path = search_path
        self.registry = {}
        self.kwargs = kwargs

    @cache
    def load(self, spec, cls=None):
        if cls is None:
            raise ValueError("Unbound template loader.")

        spec = spec.strip()

        if self.default_extension is not None and '.' not in spec:
            spec += self.default_extension

        if ':' in spec:
            spec = abspath_from_asset_spec(spec)

        if not os.path.isabs(spec):
            for path in self.search_path:
                path = os.path.join(path, spec)
                if os.path.exists(path):
                    spec = path
                    break
            else:
                raise ValueError("Template not found: %s." % spec)

        return cls(spec, search_path=self.search_path, **self.kwargs)

    def bind(self, cls):
        return functools.partial(self.load, cls=cls)


class MemoryLoader(object):
    def build(self, source, filename):
        code = compile(source, filename, 'exec')
        env = {}
        exec(code, env)
        return env

    def get(self, name):
        return None


class ModuleLoader(object):
    def __init__(self, path, remove=False):
        self.path = path
        self.remove = remove

    def __del__(self, shutil=shutil):
        if not self.remove:
            return
        try:
            shutil.rmtree(self.path)
        except:
            warnings.warn("Could not clean up temporary file path: %s" % (self.path,))

    def get(self, filename):
        path = os.path.join(self.path, filename)
        if os.path.exists(path):
            log.debug("loading module from cache: %s." % filename)
            base, ext = os.path.splitext(filename)
            return self._load(base, path)
        else:
            log.debug('cache miss: %s' % filename)

    def build(self, source, filename):
        imp.acquire_lock()
        try:
            d = self.get(filename)
            if d is not None:
                return d

            base, ext = os.path.splitext(filename)
            name = os.path.join(self.path, base + ".py")

            log.debug("writing source to disk (%d bytes)." % len(source))
            fd, fn = tempfile.mkstemp(prefix=base, suffix='.tmp', dir=self.path)
            temp = os.fdopen(fd, 'wb')
            encoded = source.encode('utf-8')
            header = encode_string("# -*- coding: utf-8 -*-" + "\n")

            try:
                try:
                    temp.write(header)
                    temp.write(encoded)
                finally:
                    temp.close()
            except:
                os.remove(fn)
                raise

            os.rename(fn, name)
            log.debug("compiling %s into byte-code..." % filename)
            py_compile.compile(name)

            return self._load(base, name)
        finally:
            imp.release_lock()

    def _load(self, base, filename):
        imp.acquire_lock()
        try:
            module = sys.modules.get(base)
            if module is None:
                f = open(filename, 'rb')
                try:
                    assert base not in sys.modules
                    module = imp.load_source(base, filename, f)
                finally:
                    f.close()
        finally:
            imp.release_lock()

        return module.__dict__
