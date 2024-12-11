import os
import sys
import tempfile
import unittest
import zipimport
from importlib.util import module_from_spec
from pathlib import Path


class LoadTests:
    def _makeOne(self, *args, **kwargs):
        klass = self._getTargetClass()
        return klass(*args, **kwargs)

    def _getTargetClass(self):
        from chameleon.loader import TemplateLoader
        return TemplateLoader

    def test_load_relative(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne(search_path=[here])
        result = self._load(loader, 'hello_world.pt')
        self.assertEqual(
            result.filename,
            os.path.join(here, 'hello_world.pt'))

    def test_load_relative_default_extension(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne([here], ".pt")
        result = self._load(loader, 'hello_world')
        self.assertEqual(
            result.filename,
            os.path.join(here, 'hello_world.pt'))

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
        self.assertEqual(
            result.filename,
            os.path.join(here, 'hello_world.pt'))

    def test_load_abs(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne()
        abs = os.path.join(here, 'hello_world.pt')
        result = self._load(loader, abs)
        self.assertEqual(result.filename, abs)

    def test_load_egg(self):
        self._test_load_package("bdist_egg", ".egg")

    def test_load_wheel(self):
        self._test_load_package("bdist_wheel", ".whl")

    def _test_load_package(self, command, pkg_extension):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_name = 'chameleon_test_pkg'
            basedir = Path(tmpdir) / pkg_name
            pkgdir = basedir / 'src' / pkg_name
            templatesdir = pkgdir / 'templates'
            templatesdir.mkdir(parents=True)

            olddir = os.getcwd()
            os.chdir(basedir)

            try:
                with open('MANIFEST.in', 'w') as f:
                    f.write('recursive-include src *.pt')

                pkgdir.joinpath('__init__.py').touch()
                with templatesdir.joinpath('test.pt').open('w') as f:
                    f.write("<html><body>${content}</body></html>")
                with templatesdir.joinpath('macro1.pt').open('w') as f:
                    f.write(
                        f'<html metal:use-macro="'
                        f'load: {pkg_name}:templates/test.pt" />'
                    )
                with templatesdir.joinpath('macro2.pt').open('w') as f:
                    f.write(
                        '<html metal:use-macro="load: test.pt" />'
                    )

                from setuptools import find_packages
                from setuptools import setup

                setup(
                    name=pkg_name,
                    version="1.0",
                    packages=find_packages('src'),
                    package_dir={'': 'src'},
                    include_package_data=True,
                    script_args=[command],
                )
            finally:
                os.chdir(olddir)

            (package_path,) = basedir.glob('dist/*' + pkg_extension)

            importer = zipimport.zipimporter(str(package_path))
            if hasattr(importer, 'find_spec'):
                spec = importer.find_spec(pkg_name)
                module = module_from_spec(spec)
                importer.exec_module(module)
                sys.modules[pkg_name] = module
            else:
                importer.load_module(pkg_name)

            try:
                self._test_pkg(pkg_name)
            finally:
                # Manually clean up archive.
                # See https://github.com/python/cpython/issues/87319.
                os.unlink(importer.archive)

                # Remove imported module.
                sys.modules.pop(pkg_name, None)

    def _test_pkg(self, pkg_name):
        loader = self._makeOne(auto_reload=True)
        # we use auto_reload to trigger a call of mtime
        result = self._load(
            loader, f'{pkg_name}:templates/test.pt')
        self.assertIsNone(result._v_last_read)
        output = result(content='foo')
        self.assertIsNotNone(result._v_last_read)
        old_v_last_read = result._v_last_read
        self.assertIn("foo", output)
        # make sure the template isn't recooked
        output = result(content='bar')
        self.assertEqual(result._v_last_read, old_v_last_read)
        macro1 = self._load(loader, f'{pkg_name}:templates/macro1.pt')
        macro1_output = macro1(content='bar')
        self.assertEqual(output, macro1_output)
        macro2 = self._load(loader, f'{pkg_name}:templates/macro2.pt')
        macro2_output = macro2(content='bar')
        self.assertEqual(output, macro2_output)


class LoadPageTests(unittest.TestCase, LoadTests):
    def _load(self, loader, spec):
        from chameleon.zpt import template
        return loader.load(spec, template.PageTemplateFile)


class ZPTLoadPageTests(unittest.TestCase, LoadTests):
    def _getTargetClass(self):
        from chameleon.zpt.loader import TemplateLoader
        return TemplateLoader

    def _load(self, loader, spec):
        return loader.load(spec)


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
        self.assertIn('test', sys.modules)
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
