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
        self.assertEqual(
            result.spec.filename,
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
            result.spec.filename,
            os.path.join(here, 'hello_world.pt'))

    def test_load_abs(self):
        import os
        here = os.path.join(os.path.dirname(__file__), "inputs")
        loader = self._makeOne()
        abs = os.path.join(here, 'hello_world.pt')
        result = self._load(loader, abs)
        self.assertEqual(result.spec.filename, abs)

    def test_load_egg(self):
        import subprocess
        import sys
        import tempfile
        import textwrap
        import zipimport
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            basedir = Path(tmpdir) / 'chameleon_test_pkg'
            pkgdir = basedir / 'src' / 'chameleon_test_pkg'
            templatesdir = pkgdir / 'templates'
            templatesdir.mkdir(parents=True)
            with basedir.joinpath('MANIFEST.in').open('w') as f:
                f.write('recursive-include src *.pt')
            with basedir.joinpath('setup.py').open('w') as f:
                f.write(textwrap.dedent("""
                    from setuptools import find_packages
                    from setuptools import setup


                    setup(
                        name="chameleon-test-pkg",
                        version="1.0",
                        packages=find_packages('src'),
                        package_dir={'': 'src'},
                        include_package_data=True)
                """))
            pkgdir.joinpath('__init__.py').touch()
            with templatesdir.joinpath('test.pt').open('w') as f:
                f.write(textwrap.dedent("""
                    <html>
                    <head><title>Test Title</title></head>
                    <body>${content}</body>
                    </html>
                """))
            try:
                subprocess.check_output(
                    ['python', 'setup.py', 'bdist_egg'],
                    cwd=basedir,
                    stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                print('\n', e.output.decode(), file=sys.stderr)
                raise
            (egg_path,) = basedir.glob('dist/*.egg')
            zipimport.zipimporter(
                str(egg_path)).load_module('chameleon_test_pkg')
            try:
                # we use auto_reload to trigger a call of mtime
                loader = self._makeOne(auto_reload=True)
                result = self._load(
                    loader, 'chameleon_test_pkg:templates/test.pt')
                self.assertIsNone(result._v_last_read)
                output = result(content='Test Content')
                self.assertIsNotNone(result._v_last_read)
                old_v_last_read = result._v_last_read
                self.assertIn("Test Title", output)
                self.assertIn("Test Content", output)
                # make sure the template isn't recooked
                output = result(content='foo')
                self.assertEqual(result._v_last_read, old_v_last_read)
            finally:
                # cleanup
                sys.modules.pop('chameleon_test_pkg', None)

    def test_load_wheel(self):
        import subprocess
        import sys
        import tempfile
        import textwrap
        import zipimport
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmpdir:
            basedir = Path(tmpdir) / 'chameleon_test_pkg'
            pkgdir = basedir / 'src' / 'chameleon_test_pkg'
            templatesdir = pkgdir / 'templates'
            templatesdir.mkdir(parents=True)
            with basedir.joinpath('MANIFEST.in').open('w') as f:
                f.write('recursive-include src *.pt')
            with basedir.joinpath('pyproject.toml').open('w') as f:
                f.write(textwrap.dedent("""
                    [build-system]
                    requires = ["setuptools"]
                    build-backend = "setuptools.build_meta"

                    [project]
                    name = "chameleon-test-pkg"
                    version = "1.0"

                    [tool.setuptools]
                    include-package-data = true

                    [tool.setuptools.packages.find]
                    where = ["src"]
                """))
            pkgdir.joinpath('__init__.py').touch()
            with templatesdir.joinpath('test.pt').open('w') as f:
                f.write(textwrap.dedent("""
                    <html>
                    <head><title>Test Title</title></head>
                    <body>${content}</body>
                    </html>
                """))
            try:
                subprocess.check_output(
                    ['python', '-m', 'build', '--no-isolation', '--wheel'],
                    cwd=basedir,
                    stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                print('\n', e.output.decode(), file=sys.stderr)
                raise
            (wheel_path,) = basedir.glob('dist/*.whl')
            zipimport.zipimporter(
                str(wheel_path)).load_module('chameleon_test_pkg')
            try:
                # we use auto_reload to trigger a call of mtime
                loader = self._makeOne(auto_reload=True)
                result = self._load(
                    loader, 'chameleon_test_pkg:templates/test.pt')
                self.assertIsNone(result._v_last_read)
                output = result(content='Test Content')
                self.assertIsNotNone(result._v_last_read)
                old_v_last_read = result._v_last_read
                self.assertIn("Test Title", output)
                self.assertIn("Test Content", output)
                # make sure the template isn't recooked
                output = result(content='foo')
                self.assertEqual(result._v_last_read, old_v_last_read)
            finally:
                # cleanup
                sys.modules.pop('chameleon_test_pkg', None)


class LoadPageTests(unittest.TestCase, LoadTests):
    def _load(self, loader, spec):
        from chameleon.zpt import template
        return loader.load(spec, template.PageTemplateFile)


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
