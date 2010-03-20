import unittest
from chameleon.i18n import i18nize
from lxml.builder import ElementMaker

E=ElementMaker(namespace=i18nize.NSMAP["xhtml"],
                   nsmap={None: i18nize.NSMAP["xhtml"]})

class HasTextTests(unittest.TestCase):
    def testNone(self):
        self.assertEqual(i18nize.hasText(None), False)

    def testWhitespace(self):
        self.assertEqual(i18nize.hasText("  \t\n"), False)

    def testHtmlComment(self):
        self.assertEqual(i18nize.hasText("<!-- this is not relevant -->"), False)

    def testExpansion(self):
        self.assertEqual(i18nize.hasText("${myprecious}"), False)

    def testPlainText(self):
        self.assertEqual(i18nize.hasText("myprecious"), True)

    def testTextAndExpansion(self):
        self.assertEqual(i18nize.hasText("myprecious ${ring}"), True)


class MustTranslateTests(unittest.TestCase):
    def testEmptyElement(self):
        self.assertEqual(i18nize.mustTranslate(E.div()), False)

    def testElementWithText(self):
        self.assertEqual(i18nize.mustTranslate(E.p("some text")), True)

    def testElementWithChild(self):
        self.assertEqual(i18nize.mustTranslate(E.div(E.span())), False)

    def testElementWithTextAfterChild(self):
        span=E.span()
        span.tail="some text"
        self.assertEqual(i18nize.mustTranslate(E.div(span)), True)

    def testGenshiReplacedContent(self):
        self.assertEqual(i18nize.mustTranslate(E.div({i18nize.qn("py", "content") : "var"})), False)
        self.assertEqual(i18nize.mustTranslate(E.div({i18nize.qn("py", "replace") : "var"})), False)

    def testTalReplacedContent(self):
        self.assertEqual(i18nize.mustTranslate(E.div({i18nize.qn("tal", "content") : "var"})), False)
        self.assertEqual(i18nize.mustTranslate(E.div({i18nize.qn("tal", "replace") : "var"})), False)



class HandleContentTests(unittest.TestCase):
    def testNoText(self):
        el=E.span()
        i18nize.handleContent(el, None)
        self.assertEqual(el.attrib, {})

    def testAddTranslate(self):
        el=E.span("some text")
        i18nize.handleContent(el, i18nize.Counter())
        self.assertEqual(el.attrib, {i18nize.ATTR_TRANSLATE: "string1"})

    def testRemoveUnneededTranslate(self):
        el=E.span({i18nize.ATTR_TRANSLATE: "name"})
        i18nize.handleContent(el, None)
        self.assertEqual(el.attrib, {})

    def testNameChild(self):
        el=E.span("some ", E.strong("text"))
        i18nize.handleContent(el, i18nize.Counter())
        self.assertEqual(el.attrib, {i18nize.ATTR_TRANSLATE: "string1"})
        self.assertEqual(el[0].attrib, {i18nize.ATTR_NAME: "sub1"})

    def testKeepExistingTranslate(self):
        el=E.span("some text", {i18nize.ATTR_TRANSLATE: "name"})
        i18nize.handleContent(el, None)
        self.assertEqual(el.attrib, {i18nize.ATTR_TRANSLATE: "name"})

    def testKeepExistingChildName(self):
        el=E.span("some ", E.strong("text", {i18nize.ATTR_NAME: "text"}))
        i18nize.handleContent(el, i18nize.Counter())
        self.assertEqual(el.attrib, {i18nize.ATTR_TRANSLATE: "string1"})
        self.assertEqual(el[0].attrib, {i18nize.ATTR_NAME: "text"})


def test_suite():
    return unittest.defaultTestLoader.loadTestsFromName(__name__)
