import zope.testing
import unittest

OPTIONFLAGS = (zope.testing.doctest.ELLIPSIS |
               zope.testing.doctest.NORMALIZE_WHITESPACE)

import chameleon.core.config

def test_suite():
    filesuites = 'template.txt', 'codegen.txt', 'translation.txt', 'filecache.txt'
    testsuites = 'translation', 'clauses', 'parsing', 'utils'

    chameleon.core.config.DISK_CACHE = False
    
    return unittest.TestSuite(
        [zope.testing.doctest.DocTestSuite(
        "chameleon.core."+doctest, optionflags=OPTIONFLAGS) \
         for doctest in testsuites] + 
        
        [zope.testing.doctest.DocFileSuite(
        doctest, optionflags=OPTIONFLAGS,
        package="chameleon.core") for doctest in filesuites]
        )

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
