import os
import imp
import sys
import py_compile
import logging
import functools

log = logging.getLogger('chameleon.loader')


def cache(func):
    def load(self, *args):
        template = self.registry.get(args)
        if template is None:
            self.registry[args] = template = func(self, *args)
        return template
    return load


class TemplateLoader(object):
    """Template loader class.

    To load templates using relative filenames, pass a sequence of
    paths (or a single path) as ``search_path``.

    Additional keyword-arguments will be passed on to the template
    constructor.
    """

    def __init__(self, search_path=None, **kwargs):
        if search_path is None:
            search_path = []
        if isinstance(search_path, basestring):
            search_path = [search_path]
        self.search_path = search_path
        self.registry = {}
        self.kwargs = kwargs

    @cache
    def load(self, filename, klass):
        if os.path.isabs(filename):
            return klass(filename, self.parser)

        for path in self.search_path:
            path = os.path.join(path, filename)
            if os.path.exists(path):
                return klass(path, **self.kwargs)

        raise ValueError("Template not found: %s." % filename)


class MemoryLoader(object):
    def build(self, source, filename):
        code = compile(source, filename, 'exec')
        env = {}
        exec(code, env)
        return env

    def get(self, name):
        return None


class ModuleLoader(object):
    def __init__(self, path):
        self.path = path

    def get(self, filename):
        path = os.path.join(self.path, filename)
        if os.path.exists(path):
            log.debug("loading module from cache: %s." % filename)
            base, ext = os.path.splitext(filename)
            imp.acquire_lock()
            try:
                module = sys.modules.get(base)
                if module is not None:
                    return module.__dict__

                return self._load(base, path)
            finally:
                imp.release_lock()

    def build(self, source, filename):
        imp.acquire_lock()
        try:
            base, ext = os.path.splitext(filename)
            name = os.path.join(self.path, base + ".py")
            assert not os.path.exists(name)
            log.debug("writing source to disk (%d bytes)." % len(source))
            f = open(name, "w")
            try:
                f.write("%s\n" % '# -*- coding: utf-8 -*-')
                f.write(source)
            finally:
                f.close()

            log.debug("compiling %s into byte-code..." % filename)
            py_compile.compile(f.name)

            return self._load(base, name)
        finally:
            imp.release_lock()

    def _load(self, base, filename):
        f = open(filename, 'rb')
        try:
            assert base not in sys.modules
            module = imp.load_source(base, filename, f)
        finally:
            f.close()

        return module.__dict__


class TemplateLoader(object):
    """Generic template loader.

    To load templates using relative filenames, pass a sequence of
    paths (or a single path) as ``search_path``; if ``auto_reload`` is
    set, templates will be reloaded when modified.

    If ``translate`` is set, it will be used to translate messages.
    """

    def __init__(self, search_path=None, auto_reload=False, translate=None):
        if search_path is None:
            search_path = []
        if isinstance(search_path, str):
            search_path = [search_path]
        self.search_path = search_path
        self.auto_reload = auto_reload
        self.registry = {}

    def bind(self, cls):
        return functools.partial(self.load, cls=cls)

    def load(self, filename, cls=None):
        inst = self.registry.get(filename)
        if inst is None:
            if os.path.isabs(filename):
                path = filename
            else:
                path = self.find(filename)

            inst = cls(path, auto_reload=self.auto_reload)
            self.registry[filename] = inst

        return inst

    def find(self, filename):
        paths = (os.path.join(path, filename) for path in self.search_path)

        for path in paths:
            if os.path.exists(path):
                return path
        else:
            raise ValueError(
                "Template not found in search path: '%s'.", filename)
