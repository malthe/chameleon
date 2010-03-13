from chameleon.core import template

import language

class GenshiTemplate(template.Template):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc

    default_parser = language.Parser()
    
    def __init__(self, body, parser=None, format=None, doctype=None):
        if parser is None:
            parser = self.default_parser
        super(GenshiTemplate, self).__init__(body, parser, format, doctype)

    def render(self, **kwargs):
        mt = kwargs['match_templates'] = language.MatchTemplates()
        result = super(GenshiTemplate, self).render(**kwargs)
        return mt.process(result)

class GenshiTemplateFile(template.TemplateFile, GenshiTemplate):
    __doc__ = template.TemplateFile.__doc__ # for Sphinx autodoc

    def __init__(self, filename, parser=None, format=None,
                 doctype=None, **kwargs):
        if parser is None:
            parser = self.default_parser
        super(GenshiTemplateFile, self).__init__(
            filename, parser, format, doctype, **kwargs)

class GenshiTextTemplate(GenshiTemplate):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = language.TextParser()
    format = 'text'

class GenshiTextTemplateFile(GenshiTemplateFile):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = language.TextParser()
    format = 'text'
