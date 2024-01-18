# flake8: noqa: F401 unused

class TestImports:
    def test_pagetemplates(self):
        from chameleon import PageTemplate
        from chameleon import PageTemplateFile
        from chameleon import PageTemplateLoader

    def test_pagetexttemplates(self):
        from chameleon import PageTextTemplate
        from chameleon import PageTextTemplateFile

    def test_exceptions(self):
        from chameleon.exc import ExpressionError

    def test_compiler_utils(self):
        from chameleon.astutil import Builtin
        from chameleon.astutil import NameLookupRewriteVisitor
        from chameleon.astutil import Symbol
        from chameleon.codegen import template
        from chameleon.compiler import ExpressionEngine
        from chameleon.compiler import ExpressionEvaluator
        from chameleon.tales import ExpressionParser
        from chameleon.utils import Scope
