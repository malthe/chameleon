import zope.testing
import unittest

OPTIONFLAGS = (zope.testing.doctest.ELLIPSIS |
               zope.testing.doctest.NORMALIZE_WHITESPACE)

import zope.component.testing

import chameleon.core.config
import chameleon.core.testing
import chameleon.zpt.language

def render_template(body, **kwargs):
    parser = chameleon.zpt.language.Parser()
    func = chameleon.core.testing.compile_template(parser, parser, body, **kwargs)
    return func(**kwargs)

def test_suite():
    filesuites = 'language.txt', 'template.txt', 'i18n.txt'
    testsuites = 'language', 'expressions'

    globs = dict(render=render_template)

    chameleon.core.config.DISK_CACHE = False
    chameleon.core.config.DEBUG_MODE = True

    return unittest.TestSuite(
        [zope.testing.doctest.DocTestSuite(
        "chameleon.zpt."+doctest, optionflags=OPTIONFLAGS) \
         for doctest in testsuites] +

        [zope.testing.doctest.DocFileSuite(
        doctest, optionflags=OPTIONFLAGS,
        globs=globs,
        package="chameleon.zpt") for doctest in filesuites]
        )

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
