"""Shared physical-page selectors for retrieval and citation verification."""
from __future__ import annotations

import re
from dataclasses import dataclass

_CARDINALS = dict(zip(
    "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
    range(1, 20), strict=True,
))
_ORDINALS = dict(zip(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth".split(),
    range(1, 20), strict=True,
))
_TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10), strict=True))
_ORDINAL_TENS = dict(zip("twentieth thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth".split(), range(20, 100, 10), strict=True))
_NUMBERS = _CARDINALS | _ORDINALS | _TENS | _ORDINAL_TENS | {"hundred": 100, "hundredth": 100}
_WORD_NUMBER = "(?:" + "|".join(sorted(_NUMBERS, key=len, reverse=True)) + ")"
NUMBER = rf"(?:\d+(?:st|nd|rd|th)?|{_WORD_NUMBER}(?:[ -](?:and[ -])?{_WORD_NUMBER}){{0,3}})"
PAGINATED_FORMATS = {"docx", "pdf", "pptx", "tif", "tiff", "png", "jpg", "jpeg", "webp", "bmp"}
_PAGE = rf"\b(?:(?P<before>{NUMBER}|last|final)\s+(?P<kind_before>page|slide)|(?P<kind_after>page|slide)\s+(?:(?:number|no\.?|#)\s*)?(?P<after>{NUMBER}|last|final))\b"
_BREAK = rf"\bafter\s+(?:the\s+)?(?:(?P<number>{NUMBER})\s+)?page[ -]break\b"
_PARAGRAPH = rf"\b(?:(?P<before>{NUMBER})\s+paragraph|paragraph\s+(?:(?:number|no\.?|#)\s*)?(?P<after>{NUMBER}))\b"


def ordinal_number(value: str) -> int | None:
    value = value.lower().strip()
    if re.fullmatch(r"\d+(?:st|nd|rd|th)?", value):
        number = int(re.sub(r"(?:st|nd|rd|th)$", "", value))
        return number if number > 0 else None
    result = 0
    for word in re.split(r"[ -]", value.replace(" and ", " ")):
        part = _NUMBERS.get(word)
        if part is None:
            return None
        result = max(1, result) * 100 if part == 100 else result + part
    return result or None


@dataclass(frozen=True, slots=True)
class PageReference:
    number: int | None = None
    last: bool = False
    slide: bool = False
    invalid: bool = False

    def resolve(self, total: int | None = None) -> int | None:
        if self.invalid:
            return None
        return total if self.last else self.number

    def matches(self, page: int, extension: str, total: int | None = None) -> bool:
        return (extension in ({"pptx"} if self.slide else PAGINATED_FORMATS)
                and self.resolve(total) == page)


def parse_page_reference(query: str) -> PageReference | None:
    lowered = query.lower()
    selectors = []
    breaks = list(re.finditer(_BREAK, lowered))
    for match in re.finditer(_PAGE, lowered):
        if any(boundary.start() <= match.start() and match.end() <= boundary.end() for boundary in breaks):
            continue
        value = match.group("before") or match.group("after")
        last = value in {"last", "final"}
        selectors.append(PageReference(number=None if last else ordinal_number(value), last=last,
                                       slide=(match.group("kind_before") or match.group("kind_after")) == "slide",
                                       invalid=not last and ordinal_number(value) is None))
    if selectors:
        first = selectors[0]
        if any((s.number, s.last) != (first.number, first.last) for s in selectors[1:]):
            return PageReference(invalid=True)
        return PageReference(first.number, first.last, any(s.slide for s in selectors), first.invalid)
    match = re.search(_BREAK, lowered)
    if match:
        number = ordinal_number(match.group("number")) if match.group("number") else 1
        return PageReference(number=number + 1 if number else None, invalid=number is None)
    return None


def without_page_reference(query: str) -> str:
    return re.sub(_PAGE, " ", re.sub(_BREAK, " ", query, flags=re.I), flags=re.I)


def parse_paragraph_number(query: str) -> int | None:
    numbers = {ordinal_number(m.group("before") or m.group("after")) for m in re.finditer(_PARAGRAPH, query, re.I)}
    if not numbers:
        return None
    # Zero is an invalid/conflicting selector, so it cannot match stored ordinals.
    if len(numbers) != 1:
        return 0
    return next(iter(numbers)) or 0


def without_paragraph_reference(query: str) -> str:
    return re.sub(_PARAGRAPH, "paragraph", query, flags=re.I)


def is_paragraph_read(query: str) -> bool:
    if not re.search(r"\bparagraph\b", query, re.I):
        return False
    residual = without_paragraph_reference(without_page_reference(query))
    filler = set("what does do did is are the a an this that on in of from at after within to for and please "
                 "paragraph say says read quote show give tell me written contain contains text content exact verbatim "
                 "word docx pdf pptx document file presentation slide page".split())
    return set(re.findall(r"[a-z0-9]+", residual.lower())) <= filler
