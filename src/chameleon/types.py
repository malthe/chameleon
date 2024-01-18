from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol
from typing import TypedDict


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection

    from chameleon.tokenize import Token


class Tokenizer(Protocol):
    def __call__(
        self,
        body: str,
        filename: str | None = None
    ) -> Token: ...


class TranslationFunction(Protocol):
    def __call__(
        self,
        msgid: str,
        *,
        domain: str | None = None,
        mapping: dict[str, Any] | None = None,
        default: str | None = None,
        context: str | None = None,
        target_language: str | None = None
    ) -> str: ...


class PageTemplateConfig(TypedDict, total=False):
    auto_reload: bool
    default_expression: str
    encoding: str
    boolean_attributes: Collection[str]
    translate: TranslationFunction
    implicit_i18n_translate: bool
    implicit_i18n_attributes: set[str]
    on_error_handler: Callable[[BaseException], object]
    strict: bool
    trim_attribute_space: bool
    restricted_namespace: bool
    tokenizer: Tokenizer
    value_repr: Callable[[object], str]
    default_marker: Any
