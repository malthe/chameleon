# flake8: noqa: F401 unused

class TestImports:
    def test_pagetemplates(self):
        from chameleon import PageTemplate
        from chameleon import PageTemplateFile
        from chameleon import PageTemplateLoader

    def test_pagetexttemplates(self):
        from chameleon import PageTextTemplate
        from chameleon import PageTextTemplateFile
