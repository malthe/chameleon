import unittest


class LoadTests:
    def _makeOne(self, search_path=None, **kwargs):
        klass = self._getTargetClass()
        return klass(search_path, **kwargs)

    def _getTargetClass(self):
        from chameleon.loader import TemplateLoader
        return TemplateLoader

    def test_load_relative(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne(search_path=[here])
        result = self._load(loader, 'hello_world.pt')
        self.assertEqual(result.filename, os.path.join(here, 'hello_world.pt'))

    def test_consecutive_loads(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne(search_path=[here])

        self.assertTrue(
            self._load(loader, 'hello_world.pt') is
            self._load(loader, 'hello_world.pt'))

    def test_load_relative_badpath_in_searchpath(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne(search_path=[os.path.join(here, 'none'), here])
        result = self._load(loader, 'hello_world.pt')
        self.assertEqual(result.filename, os.path.join(here, 'hello_world.pt'))

    def test_load_abs(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne()
        abs = os.path.join(here, 'hello_world.pt')
        result = self._load(loader, abs)
        self.assertEqual(result.filename, abs)


class LoadPageTests(unittest.TestCase, LoadTests):
    def _load(self, loader, filename):
        from chameleon.zpt import template
        return loader.load(filename, template.PageTemplateFile)


class ModuleLoadTests(unittest.TestCase):
    def _makeOne(self, *args, **kwargs):
        from chameleon.loader import ModuleLoader
        return ModuleLoader(*args, **kwargs)

    def test_build(self):
        import tempfile
        path = tempfile.mkdtemp()
        loader = self._makeOne(path)
        source = "def function(): return %r" % "\xc3\xa6\xc3\xb8\xc3\xa5"

        module = loader.build(source, "test.xml")
        result1 = module['function']()
        d = {}
        code = compile(source, 'test.py', 'exec')
        exec(code, d)
        result2 = d['function']()
        self.assertEqual(result1, result2)

        import os
        self.assertTrue("test.py" in os.listdir(path))

        import shutil
        shutil.rmtree(path)


class ZPTLoadTests(unittest.TestCase):
    def _makeOne(self, *args, **kwargs):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        from chameleon.zpt import loader
        return loader.TemplateLoader(here, **kwargs)

    def test_load_xml(self):
        loader = self._makeOne()
        template = loader.load("hello_world.pt", "xml")
        from chameleon.zpt.template import PageTemplateFile
        self.assertTrue(isinstance(template, PageTemplateFile))

    def test_load_text(self):
        loader = self._makeOne()
        template = loader.load("hello_world.txt", "text")
        from chameleon.zpt.template import PageTextTemplateFile
        self.assertTrue(isinstance(template, PageTextTemplateFile))

    def test_load_getitem_gets_xml_file(self):
        loader = self._makeOne()
        template = loader["hello_world.pt"]
        from chameleon.zpt.template import PageTemplateFile
        self.assertTrue(isinstance(template, PageTemplateFile))
