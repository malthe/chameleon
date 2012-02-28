# -*- coding: utf-8 -*-

from __future__ import with_statement

import re
import os
import sys
import shutil
import tempfile

from functools import wraps
from functools import partial

try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase


from chameleon.utils import byte_string


class Message(object):
    def __str__(self):
        return "message"


class ImportTestCase(TestCase):
    def test_pagetemplates(self):
        from chameleon import PageTemplate
        from chameleon import PageTemplateFile
        from chameleon import PageTemplateLoader

    def test_pagetexttemplates(self):
        from chameleon import PageTextTemplate
        from chameleon import PageTextTemplateFile


class TemplateFileTestCase(TestCase):
    @property
    def _class(self):
        from chameleon.template import BaseTemplateFile

        class TestTemplateFile(BaseTemplateFile):
            cook_count = 0

            def cook(self, body):
                self.cook_count += 1
                self._cooked = True

        return TestTemplateFile

    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix='chameleon-tests')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _get_temporary_file(self):
        filename = os.path.join(self.tempdir, 'template.py')
        assert not os.path.exists(filename)
        f = open(filename, 'w')
        f.flush()
        f.close()
        return filename

    def test_cook_check(self):
        fn = self._get_temporary_file()
        template = self._class(fn)
        template.cook_check()
        self.assertEqual(template.cook_count, 1)

    def test_auto_reload(self):
        fn = self._get_temporary_file()

        # set time in past
        os.utime(fn, (0, 0))

        template = self._class(fn, auto_reload=True)
        template.cook_check()

        # a second cook check makes no difference
        template.cook_check()
        self.assertEqual(template.cook_count, 1)

        # set current time on file
        os.utime(fn, None)

        # file is reloaded
        template.cook_check()
        self.assertEqual(template.cook_count, 2)

    def test_relative_is_expanded_to_cwd(self):
        template = self._class("___does_not_exist___")
        try:
            template.cook_check()
        except IOError:
            exc = sys.exc_info()[1]
            self.assertEqual(
                os.getcwd(),
                os.path.dirname(exc.filename)
                )
        else:
            self.fail("Expected OSError.")


class RenderTestCase(TestCase):
    root = os.path.dirname(__file__)

    def find_files(self, ext):
        inputs = os.path.join(self.root, "inputs")
        outputs = os.path.join(self.root, "outputs")
        for filename in sorted(os.listdir(inputs)):
            name, extension = os.path.splitext(filename)
            if extension != ext:
                continue
            path = os.path.join(inputs, filename)

            # if there's no output file, treat document as static and
            # expect intput equal to output
            import glob
            globbed = tuple(glob.iglob(os.path.join(
                outputs, "%s*%s" % (name.split('-', 1)[0], ext))))

            if not globbed:
                self.fail("Missing output for: %s." % name)

            for output in globbed:
                name, ext = os.path.splitext(output)
                basename = os.path.basename(name)
                if '-' in basename:
                    language = basename.split('-')[1]
                else:
                    language = None

                yield path, output, language


class ZopePageTemplatesTest(RenderTestCase):
    @property
    def from_string(body):
        from ..zpt.template import PageTemplate
        return partial(PageTemplate, keep_source=True)

    @property
    def from_file(body):
        from ..zpt.template import PageTemplateFile
        return partial(PageTemplateFile, keep_source=True)

    def template(body):
        def decorator(func):
            @wraps(func)
            def wrapper(self):
                template = self.from_string(body)
                return func(self, template)

            return wrapper
        return decorator

    def error(body):
        def decorator(func):
            @wraps(func)
            def wrapper(self):
                from chameleon.exc import TemplateError
                try:
                    template = self.from_string(body)
                except TemplateError:
                    exc = sys.exc_info()[1]
                    return func(self, body, exc)
                else:
                    self.fail("Expected exception.")

            return wrapper
        return decorator

    def test_syntax_error_in_strict_mode(self):
        from chameleon.exc import ExpressionError

        self.assertRaises(
            ExpressionError,
            self.from_string,
            """<tal:block replace='bad /// ' />""",
            strict=True
            )

    def test_syntax_error_in_non_strict_mode(self):
        from chameleon.exc import ExpressionError

        body = """<tal:block replace='bad /// ' />"""
        template = self.from_string(body, strict=False)

        try:
            template()
        except ExpressionError:
            exc = sys.exc_info()[1]
            self.assertTrue(body[exc.offset:].startswith('bad ///'))
        else:
            self.fail("Expected exception")

    @error("""<tal:dummy attributes=\"dummy 'dummy'\" />""")
    def test_attributes_on_tal_tag_fails(self, body, exc):
        self.assertTrue(body[exc.offset:].startswith('dummy'))

    @error("""<tal:dummy i18n:attributes=\"foo, bar\" />""")
    def test_i18n_attributes_with_non_identifiers(self, body, exc):
        self.assertTrue(body[exc.offset:].startswith('foo,'))

    @error("""<tal:dummy repeat=\"key,value mydict.items()\">""")
    def test_repeat_syntax_error_message(self, body, exc):
        self.assertTrue(body[exc.offset:].startswith('key,value'))

    def test_encoded(self):
        filename = '074-encoded-template.pt'
        with open(os.path.join(self.root, 'inputs', filename), 'rb') as f:
            body = f.read()

        self.from_string(body)

    def test_utf8_encoded(self):
        filename = '073-utf8-encoded.pt'
        with open(os.path.join(self.root, 'inputs', filename), 'rb') as f:
            body = f.read()

        self.from_string(body)

    def test_unicode_decode_error(self):
        template = self.from_file(
            os.path.join(self.root, 'inputs', 'greeting.pt')
            )

        string = native = "the artist formerly known as ƤŗíƞĆě"
        try:
            string = string.decode('utf-8')
        except AttributeError:
            pass

        class name:
            @staticmethod
            def __html__():
                # This raises a decoding exception
                string.encode('utf-8').decode('ascii')

                self.fail("Expected exception raised.")

        try:
            template(name=name)
        except UnicodeDecodeError:
            exc = sys.exc_info()[1]
            formatted = str(exc)

            # There's a marker under the expression that has the
            # unicode decode error
            self.assertTrue('^^^^^' in formatted)
            self.assertTrue(native in formatted)
        else:
            self.fail("expected error")

    def test_custom_encoding_for_str_or_bytes_in_content(self):
        string = '<div>Тест${text}</div>'
        try:
            string = string.decode('utf-8')
        except AttributeError:
            pass

        template = self.from_string(string, encoding="windows-1251")

        text = 'Тест'

        try:
            text = text.decode('utf-8')
        except AttributeError:
            pass

        rendered = template(text=text.encode('windows-1251'))

        self.assertEqual(
            rendered,
            string.replace('${text}', text)
            )

    def test_custom_encoding_for_str_or_bytes_in_attributes(self):
        string = '<img tal="Тест${text}" />'
        try:
            string = string.decode('utf-8')
        except AttributeError:
            pass

        template = self.from_string(string, encoding="windows-1251")

        text = 'Тест'

        try:
            text = text.decode('utf-8')
        except AttributeError:
            pass

        rendered = template(text=text.encode('windows-1251'))

        self.assertEqual(
            rendered,
            string.replace('${text}', text)
            )

    def test_null_translate_function(self):
        template = self.from_string('${test}', translate=None)
        rendered = template(test=object())
        self.assertTrue('object' in rendered)

    def test_object_substitution_coerce_to_str(self):
        template = self.from_string('${test}', translate=None)

        class dummy(object):
            def __repr__(inst):
                self.fail("call not expected")

            def __str__(inst):
                return '<dummy>'

        rendered = template(test=dummy())
        self.assertEqual(rendered, '&lt;dummy&gt;')

    def test_repr(self):
        template = self.from_file(
            os.path.join(self.root, 'inputs', 'hello_world.pt')
            )
        self.assertTrue(template.filename in repr(template))

    def test_underscore_variable(self):
        template = self.from_string(
            "<div tal:define=\"_dummy 'foo'\">${_dummy}</div>"
            )
        self.assertTrue(template(), "<div>foo</div>")

    def test_trim_attribute_space(self):
        document = '''<div
                  class="document"
                  id="test"
                  tal:attributes="class string:${default} test"
            />'''

        result1 = self.from_string(
            document)()

        result2 = self.from_string(
            document, trim_attribute_space=True)()

        self.assertEqual(result1.count(" "), 49)
        self.assertEqual(result2.count(" "), 4)
        self.assertTrue(" />" in result1)
        self.assertTrue(" />" in result2)

    def test_exception(self):
        from traceback import format_exception_only

        template = self.from_string(
            "<div tal:define=\"dummy foo\">${dummy}</div>"
            )
        try:
            template()
        except:
            exc = sys.exc_info()[1]
            formatted = str(exc)
            self.assertFalse('NameError:' in formatted)
            self.assertTrue('foo' in formatted)
            self.assertTrue('(1:23)' in formatted)

            formatted_exc = "\n".join(format_exception_only(type(exc), exc))
            self.assertTrue('NameError: foo' in formatted_exc)
        else:
            self.fail("expected error")

    def test_create_formatted_exception(self):
        from chameleon.utils import create_formatted_exception

        exc = create_formatted_exception(NameError('foo'), NameError, str)
        self.assertEqual(exc.args, ('foo', ))

        class MyNameError(NameError):
            def __init__(self, boo):
                NameError.__init__(self, boo)
                self.bar = boo

        exc = create_formatted_exception(MyNameError('foo'), MyNameError, str)
        self.assertEqual(exc.args, ('foo', ))
        self.assertEqual(exc.bar, 'foo')

    def test_create_formatted_exception_no_subclass(self):
        from chameleon.utils import create_formatted_exception

        class DifficultMetaClass(type):
            def __init__(self, class_name, bases, namespace):
                if not bases == (BaseException, ):
                    raise TypeError(bases)

        Difficult = DifficultMetaClass('Difficult', (BaseException, ), {'args': ()})

        exc = create_formatted_exception(Difficult(), Difficult, str)
        self.assertEqual(exc.args, ())

    def test_error_handler_makes_safe_copy(self):
        calls = []

        class TestException(Exception):
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))

        def _render(stream, econtext, rcontext):
            exc = TestException('foo', bar='baz')
            rcontext['__error__'] = ('expression', 1, 42, 'test.pt', exc),
            raise exc

        template = self.from_string("")
        template._render = _render
        try:
            template()
        except TestException:
            self.assertEqual(calls, [(('foo', ), {'bar': 'baz'})])
            exc = sys.exc_info()[1]
            formatted = str(exc)
            self.assertTrue('TestException' in formatted)
            self.assertTrue('"expression"' in formatted)
            self.assertTrue('(1:42)' in formatted)
        else:
            self.fail("unexpected error")

    def test_double_underscore_variable(self):
        from chameleon.exc import TranslationError
        self.assertRaises(
            TranslationError, self.from_string,
            "<div tal:define=\"__dummy 'foo'\">${__dummy}</div>",
            )

    def test_compiler_internals_are_disallowed(self):
        from chameleon.compiler import COMPILER_INTERNALS_OR_DISALLOWED
        from chameleon.exc import TranslationError

        for name in COMPILER_INTERNALS_OR_DISALLOWED:
            body = "<d tal:define=\"%s 'foo'\">${%s}</d>" % (name, name)
            self.assertRaises(TranslationError, self.from_string, body)

    def test_fast_translate_mapping(self):
        template = self.from_string(
            '<div i18n:translate="">'
            '<span i18n:name="name">foo</span>'
            '</div>')

        self.assertEqual(template(), '<div><span>foo</span></div>')

    def test_translate_is_not_an_internal(self):
        macro = self.from_string('<span i18n:translate="">bar</span>')
        template = self.from_string(
            '''
            <tal:defs define="translate string:">
              <span i18n:translate="">foo</span>
              <metal:macro use-macro="macro" />
            </tal:defs>
            ''')

        result = template(macro=macro)
        self.assertTrue('foo' in result)
        self.assertTrue('foo' in result)

    def test_literal_false(self):
        template = self.from_string(
            '<input type="input" tal:attributes="checked False" />'
            '<input type="input" tal:attributes="checked True" />'
            '<input type="input" tal:attributes="checked None" />'
            '<input type="input" tal:attributes="checked default" />',
            literal_false=True,
            )

        self.assertEqual(
            template(),
            '<input type="input" checked="False" />'
            '<input type="input" checked="True" />'
            '<input type="input" />'
            '<input type="input" />',
            template.source
            )

    def test_boolean_attributes(self):
        template = self.from_string(
            '<input type="input" tal:attributes="checked False" />'
            '<input type="input" tal:attributes="checked True" />'
            '<input type="input" tal:attributes="checked None" />'
            '<input type="input" tal:attributes="checked \'\'" />'
            '<input type="input" tal:attributes="checked default" />'
            '<input type="input" checked="checked" tal:attributes="checked default" />',
            boolean_attributes=set(['checked'])
            )

        self.assertEqual(
            template(),
            '<input type="input" />'
            '<input type="input" checked="checked" />'
            '<input type="input" />'
            '<input type="input" />'
            '<input type="input" />'
            '<input type="input" checked="checked" />',
            template.source
            )

    def test_default_debug_flag(self):
        from chameleon.config import DEBUG_MODE
        template = self.from_file(
            os.path.join(self.root, 'inputs', 'hello_world.pt'),
            )
        self.assertEqual(template.debug, DEBUG_MODE)
        self.assertTrue('debug' not in template.__dict__)

    def test_debug_flag_on_string(self):
        from chameleon.loader import ModuleLoader

        with open(os.path.join(self.root, 'inputs', 'hello_world.pt')) as f:
            source = f.read()

        template = self.from_string(source, debug=True)

        self.assertTrue(template.debug)
        self.assertTrue(isinstance(template.loader, ModuleLoader))

    def test_debug_flag_on_file(self):
        from chameleon.loader import ModuleLoader
        template = self.from_file(
            os.path.join(self.root, 'inputs', 'hello_world.pt'),
            debug=True,
            )
        self.assertTrue(template.debug)
        self.assertTrue(isinstance(template.loader, ModuleLoader))

    def test_tag_mismatch(self):
        from chameleon.exc import ParseError

        try:
            self.from_string("""
            <div metal:use-macro="layout">
            <div metal:fill-slot="name"></dav>
            </div>
            """)
        except ParseError:
            exc = sys.exc_info()[1]
            self.assertTrue("</dav>" in str(exc))
        else:
            self.fail("Expected error.")


class ZopeTemplatesTestSuite(RenderTestCase):
    def setUp(self):
        self.temp_path = temp_path = tempfile.mkdtemp()

        @self.addCleanup
        def cleanup(path=temp_path):
            shutil.rmtree(path)

    def test_pt_files(self):
        from ..zpt.template import PageTemplateFile

        class Literal(object):
            def __init__(self, s):
                self.s = s

            def __html__(self):
                return self.s

            def __str__(self):
                raise RuntimeError(
                    "%r is a literal." % self.s)

        from chameleon.loader import TemplateLoader
        loader = TemplateLoader(os.path.join(self.root, "inputs"))

        self.execute(
            ".pt", PageTemplateFile,
            literal=Literal("<div>Hello world!</div>"),
            content="<div>Hello world!</div>",
            message=Message(),
            load=loader.bind(PageTemplateFile),
            )

    def test_txt_files(self):
        from ..zpt.template import PageTextTemplateFile
        self.execute(".txt", PageTextTemplateFile)

    def execute(self, ext, factory, **kwargs):
        def translate(msgid, domain=None, mapping=None, context=None,
                      target_language=None, default=None):
            if default is None:
                default = str(msgid)

            if isinstance(msgid, Message):
                default = "Message"

            if mapping:
                default = re.sub(r'\${([a-z_]+)}', r'%(\1)s', default) % \
                          mapping

            if target_language is None:
                return default

            if domain is None:
                with_domain = ""
            else:
                with_domain = " with domain '%s'" % domain

            stripped = default.rstrip('\n ')
            return "%s ('%s' translation into '%s'%s)%s" % (
                stripped, msgid, target_language, with_domain,
                default[len(stripped):]
                )

        for input_path, output_path, language in self.find_files(ext):
            # Make friendly title so we can locate the generated
            # source when debugging
            self.shortDescription = lambda: input_path

            # Very implicitly enable implicit translation based on
            # a string included in the input path:
            implicit_i18n = 'implicit-i18n' in input_path
            implicit_i18n_attrs = ("alt", "title") if implicit_i18n else ()

            template = factory(
                input_path,
                keep_source=True,
                strict=False,
                implicit_i18n_translate=implicit_i18n,
                implicit_i18n_attributes=implicit_i18n_attrs,
                )

            params = kwargs.copy()
            params.update({
                'translate': translate,
                'target_language': language,
                })

            template.cook_check()

            try:
                got = template.render(**params)
            except:
                import traceback
                e = traceback.format_exc()
                self.fail("%s\n\n    Example source:\n\n%s" % (e, "\n".join(
                    ["%#03.d%s" % (lineno + 1, line and " " + line or "")
                     for (lineno, line) in
                     enumerate(template.source.split(
                         '\n'))])))

            if isinstance(got, byte_string):
                got = got.decode('utf-8')

            from doctest import OutputChecker
            checker = OutputChecker()

            if not os.path.exists(output_path):
                output = template.body
            else:
                with open(output_path, 'rb') as f:
                    output = f.read()

            from chameleon.utils import read_xml_encoding
            from chameleon.utils import detect_encoding

            if template.content_type == 'text/xml':
                encoding = read_xml_encoding(output) or \
                           template.default_encoding
            else:
                content_type, encoding = detect_encoding(
                    output, template.default_encoding)

            want = output.decode(encoding)

            if checker.check_output(want, got, 0) is False:
                from doctest import Example
                example = Example(input_path, want)
                diff = checker.output_difference(
                    example, got, 0)
                self.fail("(%s) - \n%s\n\nCode:\n%s" % (
                    input_path, diff.rstrip('\n'),
                    template.source.encode('utf-8')))
