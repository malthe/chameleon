import unittest

class TestExplicitDoctypes(unittest.TestCase):
    def test_doctype_declared_in_constructor_adds_doctype(self):
        from chameleon.core.testing import MockTemplate
        from chameleon.core import doctypes
        body = u"""\
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>
        """
        expected = u"""\
        <!DOCTYPE html PUBLIC"-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>"""
        t = MockTemplate(body, doctype=doctypes.xhtml_strict)
        self.assertEqual(norm(t.render()), norm(expected))

    def test_doctype_declared_in_constructor_overrides_template_doctype(self):
        from chameleon.core.testing import MockTemplate
        from chameleon.core import doctypes
        body = u"""\
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>
        """
        expected = u"""\
        <!DOCTYPE html PUBLIC"-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>"""
        t = MockTemplate(body, doctype=doctypes.xhtml_strict)
        self.assertEqual(norm(t.render()), norm(expected))

    def test_doctype_assigned_to_instance_overrides_constructor_doctype(self):
        from chameleon.core.testing import MockTemplate
        from chameleon.core import doctypes
        body = u"""\
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>
        """
        expected = u"""\
        <!DOCTYPE HTML PUBLIC"-//W3C//DTD HTML4.01 Transitional//EN"
        "http://www.w3.org/TR/html4/loose.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>"""
        t = MockTemplate(body, doctype=doctypes.html)
        t.doctype = doctypes.html
        self.assertEqual(norm(t.render()), norm(expected))

    def test_no_doctype_overrides_parsed_doctype(self):
        from chameleon.core.testing import MockTemplate
        from chameleon.core import doctypes
        body = u"""\
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>
        """
        expected = u"""\
        <html xmlns="http://www.w3.org/1999/xhtml">
        </html>"""
        t = MockTemplate(body, doctype=doctypes.no_doctype)
        self.assertEqual(norm(t.render()), norm(expected))

class UnicodeTortureTests(unittest.TestCase):
    def setUp(self):
        import chameleon.genshi.language
        import chameleon.core.testing
        parser = chameleon.genshi.language.Parser()
        def render_template(body, encoding='utf-8', **kwargs):
            func = chameleon.core.testing.compile_template(
                parser, parser, body, encoding=encoding, **kwargs)
            return func(**kwargs)
        self.render_template = render_template

    def test_torture(self):

        body = """\
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml"
        xmlns:py="http://genshi.edgewall.org/">
        <title>\xc2\xa9</title>
        <div id="${foo}" py:attrs="dict(label=foo)"></div>
        </html>
        """
        expected = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
        <title>\xc2\xa9</title>
        <div label="\xc2\xa9" id="\xc2\xa9"></div>
        </html>"""
        c = unicode('\xc2\xa9', 'utf-8')
        result = self.render_template(body, foo=c).encode('utf-8')
        self.assertEqual(norm(result), norm(expected))

def norm(s):
    return s.replace(' ', '').replace('\n', '')

def test_suite():
    import sys
    return unittest.findTestCases(sys.modules[__name__])
