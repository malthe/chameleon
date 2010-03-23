from chameleon.core import template
from chameleon.genshi.language import MatchTemplates
from chameleon.genshi.language import Parser
from chameleon.genshi.language import TextParser

class GenshiTemplate(template.Template):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc

    default_parser = Parser()

    def __init__(self, body, parser=None, **kwargs):
        if parser is None:
            parser = self.default_parser
        super(GenshiTemplate, self).__init__(body, parser, **kwargs)

    def render(self, *args, **kwargs):
        mt = kwargs['match_templates'] = MatchTemplates()
        result = super(GenshiTemplate, self).render(*args, **kwargs)
        return mt.process(result)

class GenshiTemplateFile(template.TemplateFile, GenshiTemplate):
    __doc__ = template.TemplateFile.__doc__ # for Sphinx autodoc

    def __init__(self, filename, parser=None, **kwargs):
        if parser is None:
            parser = self.default_parser
        super(GenshiTemplateFile, self).__init__(
            filename, parser, **kwargs)

class GenshiTextTemplate(GenshiTemplate):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = TextParser()
    format = 'text'

class GenshiTextTemplateFile(GenshiTemplateFile):
    __doc__ = template.Template.__doc__ # for Sphinx autodoc
    default_parser = TextParser()
    format = 'text'
