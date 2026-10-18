"""Chuẩn hóa text tiếng Việt trước khi tính WER (AI-11).

Áp dụng giống hệt cho reference và hypothesis. Quy tắc chi tiết và lý do nằm trong
`RULES.md`; mỗi quy tắc có test trong `tests/test_vi_normalize.py`.

    >>> normalize("Hoà chốt 25% lúc 9h30, ờ, ngày 15/10.")
    'hòa chốt hai mươi lăm phần trăm lúc chín giờ ba mươi ngày mười lăm tháng mười'
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEXICON_FILE = HERE / "lexicon.tsv"

# ------------------------------------------------------------------ số -> chữ

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
GROUP_UNITS = ["", "nghìn", "triệu", "tỷ"]
MAX_NUMBER = 10**12 - 1  # tới "chín trăm chín mươi chín tỷ..."; lớn hơn thì đọc từng chữ số


def _read_triple(n: int, full: bool) -> list[str]:
    """Đọc số 0..999. `full`: có nhóm cao hơn đứng trước, nên phải đọc đủ "không trăm"."""
    hundreds, tens, units = n // 100, (n // 10) % 10, n % 10
    words: list[str] = []
    if hundreds or full:
        words += [DIGITS[hundreds], "trăm"]
    if tens == 0:
        if units and words:
            words += ["linh", DIGITS[units]]
        elif units:
            words.append(DIGITS[units])
    elif tens == 1:
        words.append("mười")
        if units == 5:
            words.append("lăm")
        elif units:
            words.append(DIGITS[units])
    else:
        words += [DIGITS[tens], "mươi"]
        if units == 1:
            words.append("mốt")
        elif units == 5:
            words.append("lăm")
        elif units:
            words.append(DIGITS[units])
    return words


def num_to_words(n: int) -> str:
    """Đọc số nguyên không âm theo cách đọc chuẩn, ví dụ 1005 -> 'một nghìn không trăm linh năm'."""
    if n < 0:
        raise ValueError("chỉ hỗ trợ số không âm")
    if n > MAX_NUMBER:
        return digits_to_words(str(n))
    if n == 0:
        return DIGITS[0]
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    words: list[str] = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        words += _read_triple(g, full=bool(words))
        if GROUP_UNITS[i]:
            words.append(GROUP_UNITS[i])
    return " ".join(words)


def digits_to_words(s: str) -> str:
    """Đọc từng chữ số, dùng cho số điện thoại, mã số bắt đầu bằng 0, số quá lớn."""
    return " ".join(DIGITS[int(c)] for c in s if c.isdigit())


def _int_words(s: str) -> str:
    if len(s) > 1 and s.startswith("0"):
        return digits_to_words(s)
    return num_to_words(int(s))


# Số đứng riêng, không dính chữ cái (không đụng tới "mp3", "4g", "v2").
_B = r"(?<![\w])"
_E = r"(?![\w])"
_PERCENT = re.compile(_B + r"(\d+(?:,\d+)?)\s*%")
_TIME = re.compile(_B + r"(\d{1,2})(?:h|:)(\d{2})?" + _E)
_DATE_FULL = re.compile(_B + r"(\d{1,2})/(\d{1,2})/(\d{4})" + _E)
_DATE_SHORT = re.compile(_B + r"(\d{1,2})/(\d{1,2})" + _E)
_THOUSANDS = re.compile(_B + r"\d{1,3}(?:\.\d{3})+" + _E)
_DECIMAL_COMMA = re.compile(_B + r"(\d+),(\d+)" + _E)
_DECIMAL_DOT = re.compile(_B + r"(\d+)\.(\d{1,2})" + _E)
_INTEGER = re.compile(_B + r"\d+" + _E)


def _decimal(int_part: str, frac: str, sep_word: str) -> str:
    return f"{_int_words(int_part)} {sep_word} {_int_words(frac)}"


def _expand_numbers(text: str) -> str:
    text = _PERCENT.sub(lambda m: f" {_expand_numbers(m.group(1))} phần trăm ", text)
    text = _DATE_FULL.sub(
        lambda m: (
            f" {_int_words(m.group(1))} tháng {_int_words(m.group(2))}"
            f" năm {_int_words(m.group(3))} "
        ),
        text,
    )
    text = _DATE_SHORT.sub(
        lambda m: f" {_int_words(m.group(1))} tháng {_int_words(m.group(2))} ", text
    )
    text = _TIME.sub(
        lambda m: (
            f" {_int_words(m.group(1))} giờ"
            + (f" {_int_words(m.group(2))} " if m.group(2) and int(m.group(2)) else " ")
        ),
        text,
    )
    text = _THOUSANDS.sub(lambda m: f" {num_to_words(int(m.group(0).replace('.', '')))} ", text)
    text = _DECIMAL_COMMA.sub(lambda m: f" {_decimal(m.group(1), m.group(2), 'phẩy')} ", text)
    text = _DECIMAL_DOT.sub(lambda m: f" {_decimal(m.group(1), m.group(2), 'chấm')} ", text)
    return _INTEGER.sub(lambda m: f" {_int_words(m.group(0))} ", text)


# --------------------------------------------------------- kiểu đặt dấu thanh

# Âm tiết mở kết thúc bằng oa/oe/uy: đưa dấu về nguyên âm đầu ("hoà" -> "hòa").
# Không áp dụng cho "qu" + y ("quý" giữ nguyên) và âm tiết có phụ âm cuối ("hoàng").
_TONE_MOVES = {
    "oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa",
    "oè": "òe", "oé": "óe", "oẻ": "ỏe", "oẽ": "õe", "oẹ": "ọe",
    "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy",
}  # fmt: skip


def _old_style_tone(token: str) -> str:
    tail = token[-2:]
    if tail not in _TONE_MOVES:
        return token
    if tail[0] == "u" and token[-3:-2] == "q":
        return token
    return token[:-2] + _TONE_MOVES[tail]


# ------------------------------------------------------------- biến thể chính tả

SPELLING_VARIANTS = {"ngàn": "nghìn", "tỉ": "tỷ", "kĩ": "kỹ", "lí": "lý", "mĩ": "mỹ", "sỹ": "sĩ"}
FILLERS = frozenset({"ờ", "ơ", "à", "ừm", "ưm", "hừm", "uhm", "um", "hmm"})
_DIGIT_WORDS = frozenset(DIGITS)
_SCALE_WORDS = frozenset({"trăm", "nghìn", "triệu", "tỷ"})


def _canonical_number_words(tokens: list[str]) -> list[str]:
    """Gom các cách đọc số khác nhau về một dạng (RULES.md mục 4)."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        prev = out[-1] if out else ""
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if prev == "mươi" and tok == "tư":
            tok = "bốn"
        elif prev == "mươi" and tok == "một":
            tok = "mốt"
        elif prev in {"mươi", "mười"} and tok == "nhăm":
            tok = "lăm"
        elif prev == "tháng" and tok == "tư":
            tok = "bốn"
        elif prev == "tháng" and tok == "giêng":
            tok = "một"
        elif tok == "lẻ" and prev in _SCALE_WORDS and nxt in _DIGIT_WORDS:
            tok = "linh"
        elif (
            tok == "không"
            and nxt == "trăm"
            and prev in {"nghìn", "triệu", "tỷ"}
            and i + 2 < len(tokens)
            and (tokens[i + 2] in _DIGIT_WORDS or tokens[i + 2] in {"linh", "lẻ", "mười"})
        ):
            i += 2  # "một nghìn không trăm linh năm" == "một nghìn linh năm"
            continue
        out.append(tok)
        i += 1
    return out


# ------------------------------------------------------------------- lexicon


@cache
def load_lexicon(path: Path = LEXICON_FILE) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    """Đọc lexicon.tsv: `nguồn<TAB>đích`, dòng bắt đầu bằng # là chú thích.

    Nguồn được chuẩn hóa bằng chính các bước trước lexicon, nên viết hoa hay có dấu
    câu trong file đều được. Sắp xếp nguồn dài trước để khớp cụm dài nhất.
    """
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        src, dst = line.split("\t")
        entries.append((tuple(_basic(src).split()), tuple(_basic(dst).split())))
    entries.sort(key=lambda e: -len(e[0]))
    return tuple(entries)


def _apply_lexicon(tokens: list[str], lexicon) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        for src, dst in lexicon:
            if tuple(tokens[i : i + len(src)]) == src:
                out.extend(dst)
                i += len(src)
                break
        else:
            out.append(tokens[i])
            i += 1
    return out


def _remove_fillers(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in FILLERS]


# ------------------------------------------------------------------ pipeline

_TAG = re.compile(r"\[[^\]]*\]")
_SEPARATORS = re.compile(r"[-‐‑–—/_]")


def _strip_punct(text: str) -> str:
    return "".join(
        " " if unicodedata.category(c)[0] in "PS" else c for c in _SEPARATORS.sub(" ", text)
    )


def _basic(text: str) -> str:
    """Các bước 1–6: Unicode, chữ thường, bỏ tag, đổi số, bỏ dấu câu, kiểu đặt dấu."""
    text = unicodedata.normalize("NFC", text).lower()
    text = _TAG.sub(" ", text)
    text = _expand_numbers(text)
    text = _strip_punct(text)
    tokens = [_old_style_tone(t) for t in text.split()]
    tokens = [SPELLING_VARIANTS.get(t, t) for t in tokens]
    return " ".join(tokens)


def normalize(text: str, lexicon_path: Path | None = None) -> str:
    tokens = _basic(text).split()
    tokens = _canonical_number_words(tokens)
    tokens = _apply_lexicon(tokens, load_lexicon(lexicon_path or LEXICON_FILE))
    tokens = _remove_fillers(tokens)
    return " ".join(tokens)


def tokens(text: str) -> list[str]:
    """Token để tính WER: tách theo khoảng trắng sau khi chuẩn hóa (xấp xỉ âm tiết)."""
    return normalize(text).split()


def strip_diacritics(text: str) -> str:
    """Bỏ dấu thanh và dấu phụ, dùng cho "WER không dấu" để tách lỗi thanh điệu."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
