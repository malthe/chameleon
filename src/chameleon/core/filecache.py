import os
import sys
import logging
import py_compile

try:
    from hashlib import sha1 as sha
except ImportError:
    from sha import sha

try:
    import imp
except ImportError:
    imp = None

logger = logging.getLogger("Chameleon")

class TemplateRegistry(object):
    version = None
    mtime = None
    
    def __init__(self):
        self.registry = {}

    def __getitem__(self, key):
        return self.registry[key]

    def __contains__(self, key):
        if key in self.registry:
            render = self.registry[key]
            if render is None:
                self.load()
                render = self.registry.get(key)
            return render is not None
        return False

    def add(self, key, source):
        _locals = {}
        exec source in _locals
        bind = _locals['bind']
        func = bind()
        func.source = source
        self.registry[key] = func

    def clear(self):
        self.registry.clear()
        self.registry['version'] = self.version

    def load(self):
        pass
    
    def purge(self):
        self.clear()

class TemplateCache(TemplateRegistry):
    def __init__(self, filename, version):
        self.filename = filename
        self.version = version
        self.registry = {}
        try:
            self.load()
        except IOError:
            self.clear()

    def __len__(self):
        return len(self.registry) - 1

    @property
    def mtime(self):
        try:
            return os.path.getmtime(self.module_filename)
        except (IOError, OSError):
            return 0

    @property
    def module_filename(self):
        return self.filename + os.extsep + "py"

    def load(self):
        filename = self.module_filename

        try:
            if imp is not None:
                module_name = "chameleon_%s" % sha(filename).hexdigest()
                f = open(filename, 'r')
                try:
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                    module = imp.load_source(module_name, filename, f)
                finally:
                    f.close()
                registry = module.registry
            else:
                _locals = {}
                execfile(filename, _locals)
                registry = _locals['registry']

            version = registry['version']
            if version != self.version:
                raise ValueError("Version mismatch: %s != %s" % (
                    version, self.version))
        except (AttributeError, ValueError, TypeError), e:
            logger.debug(
                "Error loading cache for %s (%s)." % (self.filename, str(e)))
            self.purge()
        else:
            self.registry.clear()
            self.registry.update(registry)

    def add(self, key, source):
        """Add template to module.

        We simply append the function definition (closure inside a
        ``bind`` method) and update the registry, e.g.

          >>> registry[key] = bind()

        """

        if os.path.exists(self.module_filename):
            module = open(self.module_filename, 'a')
        else:
            module = open(self.module_filename, 'w')
            self.initialize(module)
        try:
            module.write(source+'\n')
            module.write("registry[%s] = bind()\n" % repr(key))
        finally:
            module.close()

        py_compile.compile(self.module_filename)
        self.registry[key] = None

    def initialize(self, module):
        module.write("registry = dict(version=%s)\n" % repr(self.version))

    def purge(self):
        self.clear()
        
        # write empty file
        module = open(self.module_filename, 'w')
        self.initialize(module)
        module.close()
        py_compile.compile(self.module_filename)
