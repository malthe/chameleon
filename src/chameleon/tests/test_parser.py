from unittest import TestCase

from ..namespaces import PY_NS
from ..namespaces import XML_NS
from ..namespaces import XMLNS_NS


class ParserTest(TestCase):
    def test_comment_double_hyphen_parsing(self):
        from ..parser import match_double_hyphen

        self.assertFalse(match_double_hyphen.match('->'))
        self.assertFalse(match_double_hyphen.match('-->'))
        self.assertFalse(match_double_hyphen.match('--->'))
        self.assertFalse(match_double_hyphen.match('---->'))
        self.assertFalse(match_double_hyphen.match('- >'))

        self.assertTrue(match_double_hyphen.match('-- >'))

    def test_sample_files(self):
        import os
        import traceback
        path = os.path.join(os.path.dirname(__file__), "inputs")
        for filename in os.listdir(path):
            if not filename.endswith('.html'):
                continue

            with open(os.path.join(path, filename), 'rb') as f:
                source = f.read()

            from ..utils import read_encoded
            try:
                want = read_encoded(source)
            except UnicodeDecodeError as exc:
                self.fail("{} - {}".format(exc, filename))

            from ..parser import ElementParser
            from ..tokenize import iter_xml
            try:
                tokens = iter_xml(want)
                parser = ElementParser(tokens, {
                    'xmlns': XMLNS_NS,
                    'xml': XML_NS,
                    'py': PY_NS,
                })
                elements = tuple(parser)
            except BaseException:
                self.fail(traceback.format_exc())

            output = []

            def render(kind, args):
                if kind == 'element':
                    # start tag
                    tag, end, children = args
                    output.append("%(prefix)s%(name)s" % tag)

                    for attr in tag['attrs']:
                        output.append(
                            "%(space)s"
                            "%(name)s"
                            "%(eq)s"
                            "%(quote)s"
                            "%(value)s"
                            "%(quote)s" % attr)

                    output.append("%(suffix)s" % tag)

                    # children
                    for item in children:
                        render(*item)

                    # end tag
                    output.append(
                        "%(prefix)s%(name)s%(space)s%(suffix)s" % end
                    )
                elif kind == 'text':
                    text = args[0]
                    output.append(text)
                elif kind == 'start_tag':
                    node = args[0]
                    output.append(
                        "%(prefix)s%(name)s%(space)s%(suffix)s" % node
                    )
                else:
                    raise RuntimeError("Not implemented: %s." % kind)

            for kind, args in elements:
                render(kind, args)

            got = "".join(output)

            from doctest import OutputChecker
            checker = OutputChecker()

            if checker.check_output(want, got, 0) is False:
                from doctest import Example
                example = Example(f.name, want)
                diff = checker.output_difference(
                    example, got, 0)
                self.fail("({}) - \n{}".format(f.name, diff))
