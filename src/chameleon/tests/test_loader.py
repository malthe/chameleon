import unittest


class LoadTests:
    def _makeOne(self, search_path=None, auto_reload=False, cachedir=None):
        klass = self._getTargetClass()
        return klass(search_path, auto_reload, cachedir)

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
            self._load(loader, 'hello_world.pt') is \
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


def test_suite():
    import sys
    return unittest.findTestCases(sys.modules[__name__])
