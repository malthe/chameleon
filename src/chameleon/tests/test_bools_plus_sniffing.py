import difflib
import unittest

from chameleon import PageTemplate


xml_bytes = b"""\
<?xml version="1.0" ?>
<input type="checkbox" checked="nope" tal:attributes="checked checked" />
<input type="checkbox" checked="${checked}" />
"""

xml_w_enc_bytes = b"""\
<?xml version="1.0" encoding="ascii" ?>
<input type="checkbox" checked="nope" tal:attributes="checked checked" />
<input type="checkbox" checked="${checked}" />
"""

html5_bytes = b"""\
<!DOCTYPE html>
<html>
<head>
  <title>Title of document</title>
</head>
<body>
  <form>
    <input type="checkbox" checked="nope"
           tal:attributes="checked checked" />
    <input type="checkbox" checked="${checked}" />
  </form>
</body>
</html>
"""

html5_w_ct_n_enc_bytes = b"""\
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Content-Type" content="foo/bar; charset=utf-8" />
  <title>Title of document</title>
</head>
<body>
  <form>
    <input type="checkbox" checked="nope"
           tal:attributes="checked checked" />
    <input type="checkbox" checked="${checked}" />
  </form>
</body>
</html>
"""


class BaseTestCase(unittest.TestCase):
    def get_template(self, text):
        template = PageTemplate(text)
        return template

    def get_template_bytes(self):
        return self.get_template(self.input_bytes)

    def get_template_str(self):
        return self.get_template(self.input_bytes.decode('utf-8'))

    def assert_same(self, s1, s2):
        L1 = s1.splitlines()
        L1 = list(filter(None, [' '.join(x.split()).strip() for x in L1]))
        L2 = s2.splitlines()
        L2 = list(filter(None, [' '.join(x.split()).strip() for x in L2]))
        diff = '\n'.join(list(difflib.unified_diff(L1, L2)))
        assert diff == '', diff


class XMLTestCase(BaseTestCase):

    input_bytes = xml_bytes
    encoding = None

    def test_bytes_content_type(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_type, 'text/xml')

    def test_bytes_encoding(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_encoding, 'utf-8')

    def test_str_content_type(self):
        template = self.get_template_str()
        self.assertEqual(template.content_type, 'text/xml')

    def test_str_encoding(self):
        template = self.get_template_str()
        self.assertEqual(template.content_encoding, self.encoding)

    def test_bytes_checked_true(self):
        template = self.get_template_bytes()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="True" />
        <input type="checkbox" checked="True" />
        """
        result = template(checked=True)
        self.assert_same(expected, result)

    def test_bytes_checked_false(self):
        template = self.get_template_bytes()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="False" />
        <input type="checkbox" checked="False" />
        """
        result = template(checked=False)
        self.assert_same(expected, result)

    def test_bytes_checked_None(self):
        template = self.get_template_bytes()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" />
        <input type="checkbox" />
        """
        result = template(checked=None)
        self.assert_same(expected, result)

    def test_bytes_checked_default(self):
        template = self.get_template_bytes()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="nope" />
        <input type="checkbox" />
        """
        result = template(checked=template.default_marker.value)
        self.assert_same(expected, result)

    def test_str_checked_true(self):
        template = self.get_template_str()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="True" />
        <input type="checkbox" checked="True" />
        """
        result = template(checked=True)
        self.assert_same(expected, result)

    def test_str_checked_false(self):
        template = self.get_template_str()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="False" />
        <input type="checkbox" checked="False" />
        """
        result = template(checked=False)
        self.assert_same(expected, result)

    def test_str_checked_None(self):
        template = self.get_template_str()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" />
        <input type="checkbox" />
        """
        result = template(checked=None)
        self.assert_same(expected, result)

    def test_str_checked_default(self):
        template = self.get_template_str()
        expected = """
        <?xml version="1.0" ?>
        <input type="checkbox" checked="nope" />
        <input type="checkbox" />
        """
        result = template(checked=template.default_marker.value)
        self.assert_same(expected, result)


class XMLWithEncodingTestCase(BaseTestCase):

    input_bytes = xml_w_enc_bytes
    encoding = 'ascii'

    def test_bytes_encoding(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_encoding, self.encoding)

    def test_str_encoding(self):
        template = self.get_template_str()
        self.assertEqual(template.content_encoding, self.encoding)


class HTML5TestCase(BaseTestCase):

    input_bytes = html5_bytes

    def test_bytes_content_type(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_type, 'text/html')

    def test_bytes_encoding(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_encoding, 'utf-8')

    def test_str_content_type(self):
        template = self.get_template_str()
        self.assertEqual(template.content_type, 'text/html')

    def test_str_encoding(self):
        template = self.get_template_str()
        self.assertEqual(template.content_encoding, 'utf-8')

    def test_bytes_checked_true(self):
        template = self.get_template_bytes()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" checked="checked" />
            <input type="checkbox" checked="checked" />
          </form>
        </body>
        </html>
        """
        result = template(checked=True)
        self.assert_same(expected, result)

    def test_bytes_checked_false(self):
        template = self.get_template_bytes()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=False)
        self.assert_same(expected, result)

    def test_bytes_checked_None(self):
        template = self.get_template_bytes()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=None)
        self.assert_same(expected, result)

    def test_bytes_checked_default(self):
        template = self.get_template_bytes()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" checked="nope" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=template.default_marker.value)
        self.assert_same(expected, result)

    def test_str_checked_true(self):
        template = self.get_template_str()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" checked="checked" />
            <input type="checkbox" checked="checked" />
          </form>
        </body>
        </html>
        """
        result = template(checked=True)
        self.assert_same(expected, result)

    def test_str_checked_false(self):
        template = self.get_template_str()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=False)
        self.assert_same(expected, result)

    def test_str_checked_None(self):
        template = self.get_template_str()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=None)
        self.assert_same(expected, result)

    def test_str_checked_default(self):
        template = self.get_template_str()
        expected = """
        <!DOCTYPE html>
        <html>
        <head>
          <title>Title of document</title>
        </head>
        <body>
          <form>
            <input type="checkbox" checked="nope" />
            <input type="checkbox" />
          </form>
        </body>
        </html>
        """
        result = template(checked=template.default_marker.value)
        self.assert_same(expected, result)


class HTML5WithContentTypeAndEncodingTestCase(BaseTestCase):

    input_bytes = html5_w_ct_n_enc_bytes

    def test_bytes_content_type(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_type, 'foo/bar')

    def test_bytes_encoding(self):
        template = self.get_template_bytes()
        self.assertEqual(template.content_encoding, 'utf-8')

    def test_str_content_type(self):
        template = self.get_template_str()
        self.assertEqual(template.content_type, 'foo/bar')

    def test_str_encoding(self):
        template = self.get_template_str()
        self.assertEqual(template.content_encoding, 'utf-8')
