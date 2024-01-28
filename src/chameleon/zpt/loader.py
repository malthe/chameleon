from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import overload

from chameleon.loader import TemplateLoader as BaseLoader
from chameleon.zpt import template


if TYPE_CHECKING:
    from collections.abc import Mapping
    from collections.abc import Sequence
    from typing_extensions import TypeAlias

    _FormatsMapping: TypeAlias = Mapping[str, type[template.PageTemplateFile]]


class TemplateLoader(BaseLoader):
    formats: _FormatsMapping = {
        "xml": template.PageTemplateFile,
        "text": template.PageTextTemplateFile,
    }

    default_format: Literal['xml'] = "xml"

    def __init__(
        self,
        search_path: Sequence[str] | str | None = None,
        default_extension: str | None = None,
        *,
        formats: _FormatsMapping | None = None,
        **kwargs: Any
    ) -> None:

        if formats is not None:
            self.formats = formats

        super().__init__(search_path, default_extension, **kwargs)

    @overload  # type: ignore[override]
    def load(
        self,
        filename: str,
        format: Literal['xml'] | None = None
    ) -> template.PageTemplateFile: ...

    @overload
    def load(
        self,
        filename: str,
        format: Literal['text']
    ) -> template.PageTextTemplateFile: ...

    @overload
    def load(
        self,
        filename: str,
        format: str
    ) -> template.PageTemplateFile: ...

    def load(
        self,
        filename: str,
        format: str | None = None
    ) -> template.PageTemplateFile:
        """Load and return a template file.

        The format parameter determines will parse the file. Valid
        options are `xml` and `text`.
        """

        cls = self.formats[format or self.default_format]
        return super().load(filename, cls)

    __getitem__ = load
