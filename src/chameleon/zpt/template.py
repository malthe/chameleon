from chameleon.core import template

import language

class PageTemplate(template.Template):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc

    default_parser = language.Parser()
    version = 3
    
    def __init__(self, body, parser=None, **kwargs):
        kwargs['parser']=parser is not None and parser or self.default_parser
        super(PageTemplate, self).__init__(body, **kwargs)

    def render(self, **kwargs):
        kwargs.setdefault("template", self)
        kwargs.setdefault("macros", self.macros)
        return super(PageTemplate, self).render(**kwargs)

    def render_macro(self, macro, global_scope=False, slots={}, parameters={}):
        parameters.setdefault("macros", self.macros)
        return super(PageTemplate, self).render_macro(
            macro, global_scope=global_scope, slots=slots, parameters=parameters)

class PageTemplateFile(template.TemplateFile, PageTemplate):
    __doc__ = template.TemplateFile.__doc__ # for Sphinx autodoc

    default_parser = language.Parser()

    def __init__(self, filename, parser=None, **kwargs):
        kwargs['parser']=parser is not None and parser or self.default_parser
        super(PageTemplateFile, self).__init__(filename, **kwargs)

class PageTextTemplate(PageTemplate):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = language.TextParser()
    format = 'text'

class PageTextTemplateFile(PageTemplateFile):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = language.TextParser()
    format = 'text'

