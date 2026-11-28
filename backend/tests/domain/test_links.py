import pytest

from neuroctivity.domain.links import contains_link

FULLWIDTH_DOT = chr(0xFF0E)
IDEOGRAPHIC_DOT = chr(0x3002)
CYRILLIC_A = chr(0x0430)
CYRILLIC_O = chr(0x043E)


@pytest.mark.parametrize(
    "text",
    [
        "visit example.com today",
        "https://example.org",
        "HTTP://EXAMPLE",
        "hxxp://evil",
        "ftp ://files",
        "www.something",
        "WWW.Example",
        "www2.example",
        "t.me/channel",
        "telegram.me/x",
        "wa.me /123",
        "mail.ru",
        "write to me at a@mail.ru",
        "ok.ru/group",
        "пример.рф",
        "сайт.РФ",
        "site.com.Thanks",
        "example(.)com",
        "example [dot] com",
        "example (точка) ru",
        f"example{FULLWIDTH_DOT}com",
        f"example{IDEOGRAPHIC_DOT}com",
        f"ex{CYRILLIC_A}mple.c{CYRILLIC_O}m",
        "tg://resolve?domain=x",
        "mailto:someone",
        "javascript:alert(1)",
        "data:text/html,<b>",
        "tel:+79990000000",
        "my.site.io",
        "neural.net",
        "EXAMPLE.COM",
        "short x.xyz",
        "bit.ly",
        "go to my-site.online",
    ],
)
def test_finds_a_link(text: str) -> None:
    assert contains_link(text)


@pytest.mark.parametrize(
    "text",
    [
        "т.е. хороший курс",
        "e.g. dopamine",
        "i.e. the cortex",
        "Node.js is fine",
        "версия 3.5 лучше",
        "г.Москва, курс",
        "St.Petersburg trip",
        "It was good.It helped",
        "Great course.So clear",
        "ч.т.д.",
        "и т.д.Спасибо",
        "a.m. and p.m.",
        "Ph.D level",
        "U.S. students",
        "орг.вопросы решены",
        "data: five lessons",
        "tel: none",
        "Nice.Live sessions",
        "The lesson.Me and my friend",
        "10.5 hours",
        "Mr.Smith",
        "wow...com",
        "dots com",
        "время: 12:30",
        "ratio 1:2",
        "обзор: класс",
        "сом.рыба",
        "@channel_name",
        "neuro-science course",
    ],
)
def test_does_not_mistake_ordinary_text_for_a_link(text: str) -> None:
    assert not contains_link(text)
