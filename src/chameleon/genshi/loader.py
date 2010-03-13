from chameleon.core.loader import TemplateLoader as BaseLoader
from chameleon.genshi import language
from chameleon.genshi import template


class TemplateLoader(BaseLoader):
    default_parser = language.Parser()

    formats = { "xml"  : template.GenshiTemplateFile,
                "text" : template.GenshiTextTemplateFile,
               }

    def load(self, filename, format="xml"):
        """Load and return a template file. The format parameter determines
        will parse the file. Valid options are `xml` and `text`."""
        return super(TemplateLoader, self).load(filename, self.formats[format])


