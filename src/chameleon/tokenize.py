# http://code.activestate.com/recipes/65125-xml-lexing-shallow-parsing/
# by Paul Prescod
# licensed under the PSF License
#
# modified to capture all non-overlapping parts of tokens

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import SupportsIndex
from typing import cast
from typing import overload


if TYPE_CHECKING:
    from typing_extensions import Self


class recollector:
    def __init__(self):
        self.res = {}

    def add(self, name, reg) -> None:
        re.compile(reg)  # check that it is valid
        self.res[name] = reg % self.res


collector = recollector()
a = collector.add

a("TextSE", "[^<]+")
a("UntilHyphen", "[^-]*-")
a("Until2Hyphens", "%(UntilHyphen)s(?:[^-]%(UntilHyphen)s)*-")
a("CommentCE", "%(Until2Hyphens)s>?")
a("UntilRSBs", "[^\\]]*](?:[^\\]]+])*]+")
a("CDATA_CE", "%(UntilRSBs)s(?:[^\\]>]%(UntilRSBs)s)*>")
a("S", "[ \\n\\t\\r]+")
a("Simple", "[^\"'>/]+")
a("NameStrt", "[A-Za-z_:@]|[^\\x00-\\x7F]")
a("NameChar", "[A-Za-z0-9_:.-]|[^\\x00-\\x7F]")
a("Name", "(?:%(NameStrt)s)(?:%(NameChar)s)*")
a("QuoteSE", "\"[^\"]*\"|'[^']*'")
a("DT_IdentSE", "%(S)s%(Name)s(?:%(S)s(?:%(Name)s|%(QuoteSE)s))*")
a("MarkupDeclCE", "(?:[^\\]\"'><]+|%(QuoteSE)s)*>")
a("S1", "[\\n\\r\\t ]")
a("UntilQMs", "[^?]*\\?+")
a("PI_Tail", "\\?>|%(S1)s%(UntilQMs)s(?:[^>?]%(UntilQMs)s)*>")
a("DT_ItemSE",
  "<(?:!(?:--%(Until2Hyphens)s>|[^-]%(MarkupDeclCE)s)|"
  "\\?%(Name)s(?:%(PI_Tail)s))|%%%(Name)s;|%(S)s"
  )
a("DocTypeCE",
  "%(DT_IdentSE)s(?:%(S)s)?(?:\\[(?:%(DT_ItemSE)s)*](?:%(S)s)?)?>?")
a("DeclCE",
  "--(?:%(CommentCE)s)?|\\[CDATA\\[(?:%(CDATA_CE)s)?|"
  "DOCTYPE(?:%(DocTypeCE)s)?")
a("PI_CE", "%(Name)s(?:%(PI_Tail)s)?")
a("EndTagCE", "%(Name)s(?:%(S)s)?>?")
a("AttValSE", r"\"[^\"]*\"|'[^']*'|[^\s=<>`]+")
a("ElemTagCE",
  "(%(Name)s)(?:(%(S)s)(%(Name)s)(((?:%(S)s)?=(?:%(S)s)?)"
  "(?:%(AttValSE)s|%(Simple)s)|(?!(?:%(S)s)?=)))*(?:%(S)s)?(/?>)?")
a("MarkupSPE",
  "<(?:!(?:%(DeclCE)s)?|"
  "\\?(?:%(PI_CE)s)?|/(?:%(EndTagCE)s)?|(?:%(ElemTagCE)s)?)")
a("XML_SPE", "%(TextSE)s|%(MarkupSPE)s")
a("XML_MARKUP_ONLY_SPE", "%(MarkupSPE)s")
a("ElemTagSPE", "<|%(Name)s")

re_xml_spe = re.compile(collector.res['XML_SPE'])
re_markup_only_spe = re.compile(collector.res['XML_MARKUP_ONLY_SPE'])


def iter_xml(body, filename=None):
    for match in re_xml_spe.finditer(body):
        string = match.group()
        pos = match.start()
        yield Token(string, pos, body, filename)


def iter_text(body, filename=None):
    yield Token(body, 0, body, filename)


class Token(str):
    __slots__ = "pos", "source", "filename"

    pos: int
    source: str | None
    filename: str

    def __new__(
        cls,
        string: str,
        pos: int = 0,
        source: str | None = None,
        filename: str | None = None
    ) -> Self:

        inst = str.__new__(cls, string)
        inst.pos = pos
        inst.source = source
        # convert pathlib.Path to a str, since we rely on this
        # being a string downstream
        inst.filename = filename or ""
        return inst

    @overload  # type: ignore[override]
    def __getitem__(self, index: slice) -> Token: ...

    @overload
    def __getitem__(self, index: SupportsIndex) -> str: ...

    def __getitem__(self, index: SupportsIndex | slice) -> str:
        s = str.__getitem__(self, index)
        if isinstance(index, slice):
            return Token(
                s, self.pos + (index.start or 0), self.source, self.filename)
        return s

    def __add__(self, other: str | None) -> Token:
        if other is None:
            return self

        return Token(
            str.__add__(self, other), self.pos, self.source, self.filename)

    def __eq__(self, other: object) -> bool:
        return str.__eq__(self, other)

    def __hash__(self) -> int:
        return str.__hash__(self)

    def replace(
        self,
        old: str,
        new: str,
        count: SupportsIndex = -1,
        /
    ) -> Token:
        s = str.replace(self, old, new, count)
        return Token(s, self.pos, self.source, self.filename)

    def split(  # type: ignore[override]
        self,
        sep: str | None = None,
        maxsplit: SupportsIndex = -1
    ) -> list[Token]:

        l_ = str.split(self, sep, maxsplit)
        pos = self.pos
        for i, s in enumerate(l_):
            l_[i] = Token(s, pos, self.source, self.filename)
            pos += len(s)
        return cast('list[Token]', l_)

    def strip(self, chars: str | None = None, /) -> Token:
        return self.lstrip(chars).rstrip(chars)

    def lstrip(self, chars: str | None = None, /) -> Token:
        s = str.lstrip(self, chars)
        return Token(
            s, self.pos + len(self) - len(s), self.source, self.filename)

    def rstrip(self, chars: str | None = None, /) -> Token:
        s = str.rstrip(self, chars)
        return Token(s, self.pos, self.source, self.filename)

    @property
    def location(self) -> tuple[int, int]:
        if self.source is None:
            return 0, self.pos

        body = self.source[:self.pos]
        line = body.count('\n')
        return line + 1, self.pos - body.rfind('\n', 0) - 1
