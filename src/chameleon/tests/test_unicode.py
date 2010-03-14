# -*- encoding: utf-8 -*-
import unittest

class TestUnicodeMisc(unittest.TestCase):
    def test_utf8_in_page_text_template_file(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "templates")
        from chameleon.zpt.template import PageTextTemplateFile
        t = PageTextTemplateFile(os.path.join(path, 'helloworld.txt'))
        result = t()
        self._assert_unicode_equals(
            result, u'Hello W\xf5rld!\n')

    def test_utf8_values_in_page_text_template_file(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "templates")
        from chameleon.zpt.template import PageTextTemplateFile
        t = PageTextTemplateFile(os.path.join(path, 'uglyworld.txt'))
        value = u'ä'.encode("utf-8")
        result = t(value=value)
        self._assert_unicode_equals(
            result, u'Inserting a value: ä\n')

    def test_unicode_values_in_page_text_template_file(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "templates")
        from chameleon.zpt.template import PageTextTemplateFile
        t = PageTextTemplateFile(os.path.join(path, 'uglyworld.txt'))
        value = u'ä'
        result = t(value=value)
        self._assert_unicode_equals(
            result, u'Inserting a value: ä\n')

    def _assert_unicode_equals(self, value, other):
        if not isinstance(value, unicode):
            try:
                value = value.decode('utf-8')
            except UnicodeEncodeError, e:
                self.fail(str(e))
        self.assertEqual(value, other)
