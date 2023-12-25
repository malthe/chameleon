import typing as t

if t.TYPE_CHECKING:
    from chameleon.tokenize import Token


ExpressionType = t.Literal[
    'python',
    'string',
    'not',
    'exists',
    'import',
    'structure'
]


class Tokenizer(t.Protocol):
    def __call__(
        self,
        body: str,
        filename: t.Optional[str] = None
    ) -> 'Token': ...


class TranslationFunction(t.Protocol):
    def __call__(
        self,
        msgid: str,
        *,
        domain: t.Optional[str] = None,
        mapping: t.Optional[t.Mapping[str, object]] = None,
        default: t.Optional[str] = None,
        context: t.Optional[str] = None
    ) -> str: ...


class TranslationFunctionWithTargetLanguage(t.Protocol):
    def __call__(
        self,
        msgid: str,
        *,
        domain: t.Optional[str] = None,
        mapping: t.Optional[t.Mapping[str, object]] = None,
        default: t.Optional[str] = None,
        context: t.Optional[str] = None,
        target_language: t.Optional[str] = None
    ) -> str: ...


AnyTranslationFunction = t.Union[
    TranslationFunction,
    TranslationFunctionWithTargetLanguage
]


class PageTemplateConfig(t.TypedDict, total=False):
    auto_reload: bool
    default_expression: ExpressionType
    encoding: str
    boolean_attributes: t.Collection[str]
    translate: AnyTranslationFunction
    implicit_i18n_translate: bool
    implicit_i18n_attributes: t.Set[str]
    on_error_handler: t.Callable[[BaseException], object]
    strict: bool
    trim_attribute_space: bool
    restricted_namespace: bool
    tokenizer: Tokenizer
    value_repr: t.Callable[[object], str]
    default_marker: t.Any
