import tempfile
import unittest


try:
    str = unicode
    def safe_encode(string):
        return string.decode('utf-8').encode('utf-8')
except NameError:
    def safe_encode(string):
        return string.encode('utf-8')


class TypeSniffingTestCase(unittest.TestCase):
    def get_template(self, text):
        f = tempfile.NamedTemporaryFile(suffix=".html")
        f.write(text)
        f.flush()

        self._temporary = f

        from chameleon.template import BaseTemplateFile

        class DummyTemplateFile(BaseTemplateFile):
            def cook(self, body):
                pass

        return DummyTemplateFile(f.name)

    def check_content_type(self, text, expected_type):
        from chameleon.template import BaseTemplate

        class DummyTemplate(BaseTemplate):
            def cook(self, body):
                pass

        template = DummyTemplate(text)
        self.assertEqual(template.content_type, expected_type)

    def test_sniffer_xml_ascii(self):
        self.check_content_type(
            "<?xml version='1.0' encoding='ascii'?><doc/>",
            "text/xml")
        self.check_content_type(
            "<?xml\tversion='1.0' encoding='ascii'?><doc/>",
            "text/xml")

    def test_sniffer_xml_utf8(self):
        # w/out byte order mark
        self.check_content_type(
            "<?xml version='1.0' encoding='utf-8'?><doc/>",
            "text/xml")
        self.check_content_type(
            "<?xml\tversion='1.0' encoding='utf-8'?><doc/>",
            "text/xml")
        # with byte order mark
        self.check_content_type(
            "\xef\xbb\xbf<?xml version='1.0' encoding='utf-8'?><doc/>",
            "text/xml")
        self.check_content_type(
            "\xef\xbb\xbf<?xml\tversion='1.0' encoding='utf-8'?><doc/>",
            "text/xml")

    def test_sniffer_xml_utf16_be(self):
        # w/out byte order mark
        self.check_content_type(
            "\0<\0?\0x\0m\0l\0 \0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'"
            "\0 \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>"
            "\0<\0d\0o\0c\0/\0>",
            "text/xml")
        self.check_content_type(
            "\0<\0?\0x\0m\0l\0\t\0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'"
            "\0 \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>"
            "\0<\0d\0o\0c\0/\0>",
            "text/xml")
        # with byte order mark
        self.check_content_type(
            "\xfe\xff"
            "\0<\0?\0x\0m\0l\0 \0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'"
            "\0 \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>"
            "\0<\0d\0o\0c\0/\0>",
            "text/xml")
        self.check_content_type(
            "\xfe\xff"
            "\0<\0?\0x\0m\0l\0\t\0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'"
            "\0 \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>"
            "\0<\0d\0o\0c\0/\0>",
            "text/xml")

    def test_sniffer_xml_utf16_le(self):
        # w/out byte order mark
        self.check_content_type(
            "<\0?\0x\0m\0l\0 \0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'\0"
            " \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>\0"
            "<\0d\0o\0c\0/\0>\n",
            "text/xml")
        self.check_content_type(
            "<\0?\0x\0m\0l\0\t\0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'\0"
            " \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>\0"
            "<\0d\0o\0c\0/\0>\0",
            "text/xml")
        # with byte order mark
        self.check_content_type(
            "\xff\xfe"
            "<\0?\0x\0m\0l\0 \0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'\0"
            " \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>\0"
            "<\0d\0o\0c\0/\0>\0",
            "text/xml")
        self.check_content_type(
            "\xff\xfe"
            "<\0?\0x\0m\0l\0\t\0v\0e\0r\0s\0i\0o\0n\0=\0'\01\0.\0000\0'\0"
            " \0e\0n\0c\0o\0d\0i\0n\0g\0=\0'\0u\0t\0f\0-\08\0'\0?\0>\0"
            "<\0d\0o\0c\0/\0>\0",
            "text/xml")

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
        self.check_content_type("<doc><element/></doc>",
                                "text/xml")

    def test_html_default_encoding(self):
        body = safe_encode(
            '<html><head><title>' \
            '\xc3\x90\xc2\xa2\xc3\x90\xc2\xb5' \
            '\xc3\x91\xc2\x81\xc3\x91\xc2\x82' \
            '</title></head></html>')

        template = self.get_template(body)
        self.assertEqual(template.body, body.decode('utf-8'))

    def test_html_encoding_by_meta(self):
        body = safe_encode(
            '<html><head><title>' \
            '\xc3\x92\xc3\xa5\xc3\xb1\xc3\xb2' \
            '</title><meta http-equiv="Content-Type"' \
            ' content="text/html; charset=windows-1251"/>' \
            "</head></html>")

        template = self.get_template(body)
        self.assertEqual(template.body, body.decode('windows-1251'))

    def test_xhtml(self):
        body = safe_encode(
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
