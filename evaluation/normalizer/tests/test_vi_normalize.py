"""Mỗi quy tắc trong RULES.md có ít nhất một test ở đây."""

import unicodedata

import pytest
import vi_normalize as vn
from vi_normalize import normalize


def same(a: str, b: str) -> None:
    assert normalize(a) == normalize(b), (normalize(a), normalize(b))


# 1. Unicode và chữ thường
def test_nfd_and_nfc_give_same_result():
    text = "Cuộc họp sprint planning"
    same(unicodedata.normalize("NFD", text), unicodedata.normalize("NFC", text))


def test_lowercase_and_punctuation():
    assert normalize("Chào mọi người, mình bắt đầu nhé!") == "chào mọi người mình bắt đầu nhé"


# 2. Tag
def test_bracket_tags_removed():
    assert normalize("Anh [không rõ] phụ trách") == "anh phụ trách"


# 3. Số, ngày, giờ
@pytest.mark.parametrize(
    ("n", "words"),
    [
        (0, "không"),
        (5, "năm"),
        (10, "mười"),
        (15, "mười lăm"),
        (21, "hai mươi mốt"),
        (24, "hai mươi bốn"),
        (25, "hai mươi lăm"),
        (100, "một trăm"),
        (105, "một trăm linh năm"),
        (110, "một trăm mười"),
        (1005, "một nghìn không trăm linh năm"),
        (2026, "hai nghìn không trăm hai mươi sáu"),
        (1_000_000, "một triệu"),
        (1_200_000_000, "một tỷ hai trăm triệu"),
    ],
)
def test_num_to_words(n, words):
    assert vn.num_to_words(n) == words


def test_num_to_words_rejects_negative():
    with pytest.raises(ValueError):
        vn.num_to_words(-1)


def test_huge_numbers_and_leading_zero_read_digit_by_digit():
    assert normalize("0912") == "không chín một hai"
    assert normalize("1234567890123") == vn.digits_to_words("1234567890123")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.000.000 đồng", "một triệu đồng"),
        ("3,5 tỷ", "ba phẩy năm tỷ"),
        ("bản 2.5", "bản hai chấm năm"),
        ("50%", "năm mươi phần trăm"),
        ("2,5 %", "hai phẩy năm phần trăm"),
        ("9h30", "chín giờ ba mươi"),
        ("9:30", "chín giờ ba mươi"),
        ("9h", "chín giờ"),
        ("10:00", "mười giờ"),
        ("15/10", "mười lăm tháng mười"),
        ("15/10/2026", "mười lăm tháng mười năm hai nghìn hai mươi sáu"),
    ],
)
def test_number_formats(text, expected):
    assert normalize(text) == expected


def test_digits_inside_words_are_kept():
    assert normalize("File mp3, mạng 4G, bản v2") == "file mp3 mạng 4g bản v2"


# 4. Gom cách đọc số
@pytest.mark.parametrize(
    ("spoken", "written"),
    [
        ("hai mươi tư", "24"),
        ("hai mươi một", "21"),
        ("hai mươi nhăm", "25"),
        ("một trăm lẻ năm", "105"),
        ("hai nghìn hai mươi tư", "2024"),
        ("một nghìn lẻ năm", "1005"),
        ("tháng tư", "tháng 4"),
        ("tháng giêng", "tháng 1"),
    ],
)
def test_spoken_number_variants_match_digits(spoken, written):
    same(spoken, written)


def test_number_variant_rules_do_not_touch_normal_words():
    assert normalize("thứ tư anh tư vấn số lẻ") == "thứ tư anh tư vấn số lẻ"


# 5. Dấu câu
def test_separators_become_spaces():
    assert normalize("front-end/back-end_v2") == "front end back end v2"


# 6. Kiểu đặt dấu thanh
@pytest.mark.parametrize(
    ("new_style", "old_style"),
    [("hoà", "hòa"), ("khoẻ", "khỏe"), ("thuỷ", "thủy"), ("Uỷ ban", "ủy ban"), ("loạ", "lọa")],
)
def test_tone_mark_placement(new_style, old_style):
    assert normalize(new_style) == old_style


@pytest.mark.parametrize("word", ["quý", "quỷ", "hoàng", "toán", "khuyết", "huỳnh"])
def test_tone_mark_placement_leaves_other_syllables(word):
    assert normalize(word) == word


# 7. Biến thể chính tả
def test_spelling_variants():
    same("kĩ thuật", "kỹ thuật")
    same("hàng ngàn", "hàng nghìn")
    same("bác sỹ", "bác sĩ")


# 8. Lexicon
def test_lexicon():
    assert normalize("gọi A-pi-ai rồi ô kê") == "gọi api rồi ok"
    assert normalize("Deploy lên server") == "deploy lên server"


def test_custom_lexicon(tmp_path):
    lex = tmp_path / "lex.tsv"
    lex.write_text("# chú thích\nva lô ran\tvalorant\n", encoding="utf-8")
    assert normalize("chơi Va-lô-ran", lexicon_path=lex) == "chơi valorant"


# 9. Từ đệm
def test_fillers_removed_but_u_kept():
    assert normalize("Ờ thì, à, mình ừm làm") == "thì mình làm"
    assert normalize("Ừ, được.") == "ừ được"


# 10–11. Token và WER không dấu
def test_tokens():
    assert vn.tokens("Chào, 2 bạn!") == ["chào", "hai", "bạn"]


def test_strip_diacritics():
    assert vn.strip_diacritics("đường phố hòa bình Đà Nẵng") == "duong pho hoa binh Da Nang"


# Tính chất chung
@pytest.mark.parametrize(
    "text",
    [
        "Hoà và Thuỷ chốt 25% ngân sách lúc 9h30, ờ, ngày 15/10.",
        "Anh Minh phụ trách phần API upload, hạn thứ Sáu tuần này nhé.",
        "Một nghìn lẻ năm người, 1.200 khách",
        "",
    ],
)
def test_idempotent(text):
    once = normalize(text)
    assert normalize(once) == once


def test_empty_and_whitespace():
    assert normalize("") == ""
    assert normalize("  \n\t ") == ""
    assert normalize("…!!!") == ""
