import os
import sys
import unittest
import doctest

OPTIONFLAGS = (doctest.ELLIPSIS |
               doctest.NORMALIZE_WHITESPACE)

class UTF8DocTestParser(doctest.DocTestParser):
    def parse(self, string, name='<string>'):
        return doctest.DocTestParser.parse(self, string.decode('utf-8'), name)

def docfilesuite(func):
    def handler(cls):
        path = func(cls)
        parser = UTF8DocTestParser()
        return doctest.DocFileSuite(
            path, optionflags=OPTIONFLAGS, package="chameleon", parser=parser)

    handler.__name__ = func.__name__
    return handler

class CoreTests(unittest.TestCase):
    def __new__(self, test):
        from chameleon.core import config
        config.DISK_CACHE = False
        config.DEBUG_MODE = True
        config.STRICT_MODE = True
        return getattr(self, test)()

    @classmethod
    @docfilesuite
    def test_template(cls):
        return os.path.join('core', 'template.txt')

    @classmethod
    @docfilesuite
    def test_codegen(cls):
        return os.path.join('core', 'codegen.txt')

    @classmethod
    @docfilesuite
    def test_translation(cls):
        return os.path.join('core', 'translation.txt')

    @classmethod
    @docfilesuite
    def test_filecache(cls):
        return os.path.join('core', 'filecache.txt')

    @classmethod
    def test_translation_module(cls):
        from chameleon.core import translation
        return doctest.DocTestSuite(translation, optionflags=OPTIONFLAGS)

    @classmethod
    def test_clauses_module(cls):
        from chameleon.core import clauses
        return doctest.DocTestSuite(clauses, optionflags=OPTIONFLAGS)

    @classmethod
    def test_parsing_module(cls):
        from chameleon.core import parsing
        return doctest.DocTestSuite(parsing, optionflags=OPTIONFLAGS)

    @classmethod
    def test_utils_module(cls):
        from chameleon.core import utils
        return doctest.DocTestSuite(utils, optionflags=OPTIONFLAGS)

class ZopePageTemplatesTests(unittest.TestCase):
    def __new__(self, test):
        return getattr(self, test)()

    @classmethod
    @docfilesuite
    def test_language(cls):
        return os.path.join('zpt', 'language.txt')

    @classmethod
    @docfilesuite
    def test_template(cls):
        return os.path.join('zpt', 'template.txt')

    @classmethod
    @docfilesuite
    def test_i18n(cls):
        return os.path.join('zpt', 'i18n.txt')

    @classmethod
    def test_language_module(cls):
        from chameleon.zpt import language
        return doctest.DocTestSuite(language, optionflags=OPTIONFLAGS)

    @classmethod
    def test_expressions_module(cls):
        from chameleon.zpt import expressions
        return doctest.DocTestSuite(expressions, optionflags=OPTIONFLAGS)

class GenshiTemplatesTests(unittest.TestCase):
    def __new__(self, test):
        return getattr(self, test)()

    @classmethod
    @docfilesuite
    def test_language(cls):
        return os.path.join('genshi', 'language.txt')

    @classmethod
    @docfilesuite
    def test_template(cls):
        return os.path.join('genshi', 'template.txt')

    @classmethod
    @docfilesuite
    def test_i18n(cls):
        return os.path.join('genshi', 'i18n.txt')

    @classmethod
    def test_language_module(cls):
        from chameleon.genshi import language
        return doctest.DocTestSuite(language, optionflags=OPTIONFLAGS)

    @classmethod
    def test_expressions_module(cls):
        from chameleon.genshi import expressions
        return doctest.DocTestSuite(expressions, optionflags=OPTIONFLAGS)
