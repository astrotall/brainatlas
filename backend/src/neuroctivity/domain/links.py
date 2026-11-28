import re
import unicodedata

EXTRA_DOTS = str.maketrans(dict.fromkeys((chr(0x3002), chr(0xFF61), chr(0xFE52), chr(0x2024)), "."))
BRACKETED_DOT = re.compile(r"\s*[\[\(\{]\s*(?:\.|dot|точка)\s*[\]\)\}]\s*", re.IGNORECASE)

SCHEME = re.compile(
    r"[a-z][a-z0-9+.\-]{0,30}\s*:\s*//"
    r"|\b(?:mailto|javascript|vbscript)\s*:"
    r"|\bdata\s*:\s*[a-z]+/"
    r"|\btel\s*:\s*\+?\d",
    re.IGNORECASE,
)
WWW = re.compile(r"(?<![\w.])www\d{0,3}\.", re.IGNORECASE)
MESSENGER = re.compile(r"(?<![\w.])(?:t|telegram|wa|vk)\.me\s*/", re.IGNORECASE)
DOTTED_RUN = re.compile(r"(?<![\w.\-])[\w\-]+(?:\.[\w\-]+)+")
LETTERS_ONLY = re.compile(r"[^\W\d_]{2,24}")

ANY_CASE_TLDS = frozenset(
    {"com", "net", "org", "ru", "su", "ua", "kz", "uk", "de", "fr", "xyz", "рф", "рус", "укр", "бел", "срб"}
)
LOWERCASE_TLDS = frozenset(
    {
        "io",
        "co",
        "me",
        "to",
        "tv",
        "cc",
        "ws",
        "ly",
        "gg",
        "ai",
        "fm",
        "in",
        "is",
        "it",
        "at",
        "be",
        "by",
        "no",
        "so",
        "do",
        "us",
        "my",
        "am",
        "as",
        "eu",
        "cn",
        "jp",
        "es",
        "pl",
        "nl",
        "ch",
        "se",
        "ca",
        "au",
        "info",
        "biz",
        "online",
        "site",
        "top",
        "shop",
        "store",
        "app",
        "dev",
        "link",
        "click",
        "club",
        "live",
        "pro",
        "edu",
        "gov",
        "news",
        "blog",
        "page",
        "website",
        "space",
        "media",
        "tech",
        "сайт",
        "онлайн",
    }
)
CYRILLIC_LOOKALIKES = str.maketrans("асеоркхуміт", "aceopkxymit")


def comparable(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).translate(EXTRA_DOTS)
    return BRACKETED_DOT.sub(".", folded)


def has_latin_letter(label: str) -> bool:
    return any("a" <= character <= "z" for character in label)


def is_domain_suffix(label: str) -> bool:
    if not LETTERS_ONLY.fullmatch(label):
        return False
    lowered = label.lower()
    if has_latin_letter(lowered):
        lowered = lowered.translate(CYRILLIC_LOOKALIKES)
    if lowered in ANY_CASE_TLDS:
        return True
    return lowered in LOWERCASE_TLDS and label == label.lower()


def contains_domain(text: str) -> bool:
    return any(
        is_domain_suffix(label) for run in DOTTED_RUN.finditer(text) for label in run.group().split(".")[1:]
    )


def contains_link(text: str) -> bool:
    candidate = comparable(text)
    patterns = (SCHEME, WWW, MESSENGER)
    return any(pattern.search(candidate) for pattern in patterns) or contains_domain(candidate)
