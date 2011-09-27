from __future__ import with_statement

import os
import unittest
import tempfile
import shutil

from chameleon.utils import unicode_string
from chameleon.utils import encode_string


class TypeSniffingTestCase(unittest.TestCase):
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

    def get_template(self, text):
        fn = self._get_temporary_file()

        with open(fn, 'wb') as tmpfile:
            tmpfile.write(text)

        from chameleon.template import BaseTemplateFile

        class DummyTemplateFile(BaseTemplateFile):
            def cook(self, body):
                self.body = body

        template = DummyTemplateFile(fn)
        template.cook_check()
        return template

    def check_content_type(self, text, expected_type):
        from chameleon.utils import read_bytes
        content_type = read_bytes(text, 'ascii')[2]
        self.assertEqual(content_type, expected_type)

    def test_xml_encoding(self):
        from chameleon.utils import xml_prefixes

        document1 = unicode_string(
            "<?xml version='1.0' encoding='ascii'?><doc/>"
            )
        document2 = unicode_string(
            "<?xml\tversion='1.0' encoding='ascii'?><doc/>"
            )

        for bom, encoding in xml_prefixes:
            try:
                "".encode(encoding)
            except LookupError:
                # System does not support this encoding
                continue

            self.check_content_type(document1.encode(encoding), "text/xml")
            self.check_content_type(document2.encode(encoding), "text/xml")

    HTML_PUBLIC_ID = "-//W3C//DTD HTML 4.01 Transitional//EN"
    HTML_SYSTEM_ID = "http://www.w3.org/TR/html4/loose.dtd"

    # Couldn't find the code that handles this... yet.
    # def test_sniffer_html_ascii(self):
    #     self.check_content_type(
    #         "<!DOCTYPE html [ SYSTEM '%s' ]><html></html>"
    #         % self.HTML_SYSTEM_ID,
    #         "text/html")
    #     self.check_content_type(
    #         "<html><head><title>sample document</title></head></html>",
    #         "text/html")

    # TODO: This reflects a case that simply isn't handled by the
    # sniffer; there are many, but it gets it right more often than
    # before.
    def donttest_sniffer_xml_simple(self):
        self.check_content_type("<doc><element/></doc>", "text/xml")

    def test_html_default_encoding(self):
        body = encode_string(
            '<html><head><title>' \
            '\xc3\x90\xc2\xa2\xc3\x90\xc2\xb5' \
            '\xc3\x91\xc2\x81\xc3\x91\xc2\x82' \
            '</title></head></html>')

        template = self.get_template(body)
        self.assertEqual(template.body, body.decode('utf-8'))

    def test_html_encoding_by_meta(self):
        body = encode_string(
            '<html><head><title>' \
            '\xc3\x92\xc3\xa5\xc3\xb1\xc3\xb2' \
            '</title><meta http-equiv="Content-Type"' \
            ' content="text/html; charset=windows-1251"/>' \
            "</head></html>")

        template = self.get_template(body)
        self.assertEqual(template.body, body.decode('windows-1251'))

    def test_xhtml(self):
        body = encode_string(
            '<html><head><title>' \
            '\xc3\x92\xc3\xa5\xc3\xb1\xc3\xb2' \
            '</title><meta http-equiv="Content-Type"' \
            ' content="text/html; charset=windows-1251"/>' \
            "</head></html>")

        template = self.get_template(body)
        self.assertEqual(template.body, body.decode('windows-1251'))


def test_suite():
    return unittest.makeSuite(TypeSniffingTestCase)

if __name__ == "__main__":
    unittest.main(defaultTest="test_suite")
