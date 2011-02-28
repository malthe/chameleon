from chameleon.loader import TemplateLoader as BaseLoader
from chameleon.zpt import template


class TemplateLoader(BaseLoader):
    formats = {
        "xml": template.PageTemplateFile,
        "text": template.PageTextTemplateFile,
        }

    default_format = "xml"

    def load(self, filename, format=None):
        """Load and return a template file.

        The format parameter determines will parse the file. Valid
        options are `xml` and `text`.
        """

        cls = self.formats[format or self.default_format]
        return super(TemplateLoader, self).load(filename, cls)

    __getitem__ = load
