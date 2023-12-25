import typing as t

from chameleon.loader import TemplateLoader as BaseLoader
from chameleon.zpt import template


_FormatsMapping = t.Mapping[str, t.Type[template.PageTemplateFile]]


class TemplateLoader(BaseLoader):
    formats: _FormatsMapping = {
        "xml": template.PageTemplateFile,
        "text": template.PageTextTemplateFile,
    }

    default_format: t.Literal['xml'] = "xml"

    def __init__(
        self,
        search_path: t.Union[t.Sequence[str], str, None] = None,
        *,
        formats: t.Optional[_FormatsMapping] = None,
        **kwargs: t.Any
    ) -> None:

        if formats is not None:
            self.formats = formats

        super().__init__(search_path, **kwargs)

    @t.overload  # type: ignore[override]
    def load(
        self,
        filename: str,
        format: t.Union[None, t.Literal['xml']] = None
    ) -> template.PageTemplateFile: ...

    @t.overload
    def load(
        self,
        filename: str,
        format: t.Literal['text']
    ) -> template.PageTextTemplateFile: ...

    @t.overload
    def load(
        self,
        filename: str,
        format: str
    ) -> template.PageTemplateFile: ...

    def load(
        self,
        filename: str,
        format: t.Union[str, None] = None
    ) -> template.PageTemplateFile:
        """Load and return a template file.

        The format parameter determines will parse the file. Valid
        options are `xml` and `text`.
        """

        cls = self.formats[format or self.default_format]
        return super().load(filename, cls)

    __getitem__ = load
