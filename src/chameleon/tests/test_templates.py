import os
import re
import shutil
import sys
import tempfile
from functools import partial
from functools import wraps
from unittest import TestCase

from chameleon.exc import RenderError
from chameleon.tales import DEFAULT_MARKER


class Message:
    def __str__(self):
        return "message"


class ImportTestCase(TestCase):
    def test_pagetemplates(self):
        from chameleon import PageTemplate  # noqa: F401 unused
        from chameleon import PageTemplateFile  # noqa: F401 unused
        from chameleon import PageTemplateLoader  # noqa: F401 unused

    def test_pagetexttemplates(self):
        from chameleon import PageTextTemplate  # noqa: F401 unused
        from chameleon import PageTextTemplateFile  # noqa: F401 unused


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
        except OSError as exc:
            self.assertEqual(
                os.getcwd(),
                os.path.dirname(exc.filename)
            )
        else:
            self.fail("Expected OSError.")


class RenderTestCase(TestCase):
    root = os.path.dirname(__file__)
    maxDiff = 4096

    def find_files(self, ext):
        inputs = os.path.join(self.root, "inputs")
        outputs = os.path.join(self.root, "outputs")
        for filename in sorted(os.listdir(inputs)):
            name, extension = os.path.splitext(filename)
            if extension != ext:
                continue
            path = os.path.join(inputs, filename)

            # if there's no output file, treat document as static and
            # expect input equal to output
            import glob
            globbed = tuple(glob.iglob(os.path.join(
                outputs, "{}*{}".format(name.split('-', 1)[0], ext))))

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
                    self.from_string(body)
                except TemplateError as exc:
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
        except ExpressionError as exc:
            self.assertTrue(body[exc.offset:].startswith('bad ///'))
        else:
            self.fail("Expected exception")

    def test_exists_error_leak(self):
        body = '''\
        <?xml version="1.0"?>
        <root>
        <one tal:condition="exists: var_does_not_exists" />
        <two tal:attributes="my_attr dict()['key-does-not-exist']" />
        </root>'''
        template = self.from_string(body, strict=False)
        try:
            template()
        except RenderError as exc:
            self.assertNotIn('var_does_not_exists', str(exc))
        else:
            self.fail("Expected exception")

    def test_sys_exc_info_is_clear_after_pipe(self):
        body = (
            '<div tal:content="y|nothing"></div><span tal:content="error()" />'
        )
        template = self.from_string(body, strict=False)

        got = template.render(error=sys.exc_info)
        self.assertTrue('<span>(None, None, None)</span>' in got)

    def test_render_macro_include_subtemplate_containing_error(self):
        macro_inner = self.from_string(
            '''<two tal:attributes="my_attr dict()['key-does-not-exist']" />'''
        )
        macro_wrap = self.from_string(
            '''<one tal:content="macro_inner()" />''')
        template = self.from_string(
            '''
            <tal:defs define="translate string:">
              <span i18n:translate="">foo</span>
              <metal:macro use-macro="macro" />
            </tal:defs>
            ''')
        try:
            template(macro=macro_wrap, macro_inner=macro_inner)
        except RenderError as exc:
            self.assertTrue(isinstance(exc, KeyError))
            self.assertIn(''''key-does-not-exist'

 - Expression: "dict()['key-does-not-exist']"
 - Filename:   <string>
 - Location:   (line 1: col 29)
 - Expression: "macro_inner()"
 - Filename:   <string>
 - Location:   (line 1: col 18)
 - Expression: "macro"
 - Filename:   <string>
 - Location:   (line 4: col 38)
''', str(exc))
        else:
            self.fail("Expected exception")

    def test_render_error_macro_include(self):
        body = """<metal:block use-macro='"bad"' />"""
        template = self.from_string(body, strict=False)

        try:
            template()
        except RenderError as exc:
            self.assertTrue(isinstance(exc, AttributeError))
            self.assertIn('bad', str(exc))
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

    @error('''<tal:dummy><p i18n:translate="mymsgid">
            <span i18n:name="repeat"/><span i18n:name="repeat"/>
            </p></tal:dummy>''')
    def test_repeat_i18n_name_error(self, body, exc):
        self.assertTrue(body[exc.offset:].startswith(
            'repeat'), body[exc.offset:])

    @error('''<tal:dummy>
            <span i18n:name="not_in_translation"/>
            </tal:dummy>''')
    def test_i18n_name_not_in_translation_error(self, body, exc):
        self.assertTrue(body[exc.offset:].startswith('not_in_translation'))

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

    def test_recursion_error(self):
        template = self.from_string(
            '<div metal:define-macro="main" '
            'metal:use-macro="template.macros.main" />'
        )
        self.assertRaises(RecursionError, template)
        try:
            template()
        except RecursionError as exc:
            self.assertFalse(isinstance(exc, RenderError))

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
        except UnicodeDecodeError as exc:
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

    def test_on_error_handler(self):
        exc = []
        handler = exc.append
        template = self.from_string(
            '<tal:block on-error="string:error">${test}</tal:block>',
            on_error_handler=handler
        )
        template()
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc[0].__class__.__name__, "NameError")

    def test_object_substitution_coerce_to_str(self):
        template = self.from_string('${test}', translate=None)

        class dummy:
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
        except Exception as exc:
            self.assertIn(RenderError, type(exc).__bases__)
            formatted = str(exc)
            self.assertFalse('NameError:' in formatted)
            self.assertTrue('foo' in formatted)
            self.assertTrue('(line 1: col 23)' in formatted)

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

        Difficult = DifficultMetaClass(
            'Difficult', (BaseException, ), {'args': ()})

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
        except TestException as exc:
            self.assertEqual(calls, [(('foo', ), {'bar': 'baz'})])
            formatted = str(exc)
            self.assertTrue('TestException' in formatted)
            self.assertTrue('"expression"' in formatted)
            self.assertTrue('(line 1: col 42)' in formatted)
        else:
            self.fail("unexpected error")

    def test_double_underscore_variable(self):
        from chameleon.exc import TranslationError
        self.assertRaises(
            TranslationError, self.from_string,
            "<div tal:define=\"__dummy 'foo'\">${__dummy}</div>",
        )

    def test_disable_comment_interpolation(self):
        template = self.from_string(
            '<!-- ${"Hello world"} -->',
            enable_comment_interpolation=False
        )
        self.assertEqual(template(), '<!-- ${"Hello world"} -->')

    def test_compiler_internals_are_disallowed(self):
        from chameleon.compiler import COMPILER_INTERNALS_OR_DISALLOWED
        from chameleon.exc import TranslationError

        for name in COMPILER_INTERNALS_OR_DISALLOWED:
            body = "<d tal:define=\"{} 'foo'\">${{{}}}</d>".format(name, name)
            self.assertRaises(TranslationError, self.from_string, body)

    def test_simple_translate_mapping(self):
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

    def test_default_marker(self):
        template = self.from_string('<span tal:replace="id(default)" />')
        self.assertEqual(
            template(),
            str(id(DEFAULT_MARKER)),
            template.source
        )

    def test_boolean_attributes(self):
        template = self.from_string(
            '<input type="input" tal:attributes="checked False" />'
            '<input type="input" tal:attributes="checked True" />'
            '<input type="input" tal:attributes="checked None" />'
            '<input type="input" tal:attributes="checked \'\'" />'
            '<input type="input" tal:attributes="checked default" />'
            '<input type="input" checked="checked" tal:attributes="checked default" />',  # noqa: E501 line too long
            boolean_attributes={
                'checked'})

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
        except ParseError as exc:
            self.assertTrue("</dav>" in str(exc))
        else:
            self.fail("Expected error.")

    def test_f_strings(self):
        from math import pi
        from math import sin
        template = self.from_string('${f"sin({a}) is {sin(a):.3}"}')
        rendered = template(sin=sin, a=pi)
        self.assertEqual('sin(3.141592653589793) is 1.22e-16', rendered)

    def test_windows_line_endings(self):
        template = self.from_string('<span id="span_id"\r\n'
                                    '      class="foo"\r\n'
                                    '      tal:content="string:bar"/>')
        self.assertEqual(template(),
                         '<span id="span_id"\r\n'
                         '      class="foo">bar</span>')

    def test_digest(self):
        # Make sure ``digest`` doesn't error out when ``filename`` is something
        # other than a simple string
        data = '<html></html>'
        template = self.from_string(data)
        template.filename = None
        self.assertTrue(template.digest(data, []))

        template.filename = ''
        self.assertTrue(template.digest(data, []))


class ZopeTemplatesTestSuite(RenderTestCase):
    def setUp(self):
        self.temp_path = temp_path = tempfile.mkdtemp()

        @self.addCleanup
        def cleanup(path=temp_path):
            shutil.rmtree(path)

    def test_pt_files(self):
        from ..zpt.template import PageTemplateFile

        class Literal:
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

            if context is None:
                with_context = ""
            else:
                with_context = ", context '%s'" % context

            stripped = default.rstrip('\n ')
            return "{} ('{}' translation into '{}'{}{}){}".format(
                stripped, msgid, target_language, with_domain, with_context,
                default[len(stripped):]
            )

        for input_path, output_path, language in self.find_files(ext):
            # Make friendly title so we can locate the generated
            # source when debugging
            self.shortDescription = lambda: input_path

            # When input path contains the string 'implicit-i18n', we
            # enable "implicit translation".
            implicit_i18n = 'implicit-i18n' in input_path
            implicit_i18n_attrs = ("alt", "title") if implicit_i18n else ()

            enable_data_attributes = 'data-attributes' in input_path

            template = factory(
                input_path,
                keep_source=True,
                strict=False,
                implicit_i18n_translate=implicit_i18n,
                implicit_i18n_attributes=implicit_i18n_attrs,
                enable_data_attributes=enable_data_attributes,
            )

            params = kwargs.copy()
            params.update({
                'translate': translate,
                'target_language': language,
            })

            template.cook_check()

            try:
                got = template.render(**params)
            except BaseException:
                import traceback
                e = traceback.format_exc()
                self.fail("{}\n\n    Example source:\n\n{}".format(
                    e,
                    "\n".join(
                        ["%#03.d%s" % (lineno + 1, line and " " + line or "")
                         for (lineno, line) in enumerate(template.source.split(
                            '\n'))])))

            if isinstance(got, bytes):
                got = got.decode('utf-8')

            from doctest import OutputChecker
            checker = OutputChecker()

            if not os.path.exists(output_path):
                output = template.body
            else:
                with open(output_path, 'rb') as f:
                    output = f.read()

            from chameleon.utils import detect_encoding
            from chameleon.utils import read_xml_encoding

            if template.content_type == 'text/xml':
                encoding = read_xml_encoding(output) or \
                    template.default_encoding
            else:
                content_type, encoding = detect_encoding(
                    output, template.default_encoding)

            # Newline normalization across platforms
            want = '\n'.join(output.decode(encoding).splitlines())
            got = '\n'.join(got.splitlines())

            if checker.check_output(want, got, 0) is False:
                from doctest import Example
                example = Example(input_path, want)
                diff = checker.output_difference(
                    example, got, 0)
                source = template.source
                self.fail("({}) - \n{}\n\nCode:\n{}".format(
                    input_path, diff.rstrip('\n'),
                    source))
