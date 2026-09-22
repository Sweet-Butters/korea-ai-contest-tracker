import datetime as dt
import html
import re
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today() -> dt.date:
    return dt.datetime.now(KST).date()


def clean(s) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def iso(d: dt.date | None) -> str | None:
    return d.isoformat() if d else None


def from_epoch_ms(v) -> str | None:
    if not v:
        return None
    return dt.datetime.fromtimestamp(int(v) / 1000, KST).date().isoformat()


def from_dday(text: str | None, base: dt.date | None = None) -> str | None:
    """'D-12' -> base+12 days; 'D-day'/'오늘마감' -> base."""
    base = base or today()
    if not text:
        return None
    m = re.search(r"D\s*-\s*(\d+)", text, re.I)
    if m:
        return iso(base + dt.timedelta(days=int(m.group(1))))
    if re.search(r"D-?day|오늘", text, re.I):
        return iso(base)
    return None


_FULL = re.compile(r"(20\d\d)[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")
_SHORT = re.compile(r"(?<!\d)(\d{1,2})[./월]\s*(\d{1,2})일?(?!\d)")


def dates_in(text: str | None, year_hint: int | None = None) -> list[str]:
    """All dates mentioned in free text, as ISO strings. Month/day without a year gets year_hint."""
    if not text:
        return []
    out = []
    for y, m, d in _FULL.findall(text):
        try:
            out.append(dt.date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    rest = _FULL.sub(" ", text)
    y = year_hint or today().year
    for m, d in _SHORT.findall(rest):
        try:
            out.append(dt.date(y, int(m), int(d)).isoformat())
        except ValueError:
            pass
    return out


def deadline_from_text(text: str | None, base: dt.date | None = None) -> str | None:
    """Best-effort deadline from phrases like '10월 5일까지', '~10/5', '마감 10.5'."""
    if not text:
        return None
    base = base or today()
    pat = re.compile(r"(?:~\s*|마감\s*[:：]?\s*)((?:20\d\d[.\-/년]\s*)?\d{1,2}[./월]\s*\d{1,2}일?)|((?:20\d\d[.\-/년]\s*)?\d{1,2}[./월]\s*\d{1,2}일?)\s*\S{0,6}까지")
    for m in pat.finditer(text):
        ds = dates_in(m.group(1) or m.group(2), base.year)
        if ds:
            d = dt.date.fromisoformat(ds[0])
            # "1월 10일까지" written in November means next year.
            if d < base - dt.timedelta(days=120):
                d = d.replace(year=d.year + 1)
            return d.isoformat()
    m = re.search(r"(?<![\d월/.])(\d{1,2})일\s*\S{0,6}까지", text)  # "오는 30일까지": this month, or next
    if m:
        day = int(m.group(1))
        y, mo = base.year, base.month
        if day < base.day:
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        try:
            return dt.date(y, mo, day).isoformat()
        except ValueError:
            return None
    return None
