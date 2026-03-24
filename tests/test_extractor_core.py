from extractor import (
    classify_entry,
    get_normalized_subcategory_rules,
    money_to_float,
    parse_period_from_text,
)


def test_parse_period_from_period_token() -> None:
    text = "PERIODO MENS 01 DIC 25 a 31 DIC 25"
    year, month, meta = parse_period_from_text(text)
    assert year == 2025
    assert month == 12
    assert meta["period_token"] == "MENS 01 DIC 25"


def test_parse_period_from_date_token() -> None:
    text = "FECHA 31 DICIEMBRE 2025"
    year, month, meta = parse_period_from_text(text)
    assert year == 2025
    assert month == 12
    assert meta["date_token"] == "31 DICIEMBRE 2025"


def test_money_to_float_spanish_format() -> None:
    assert money_to_float("1.234,56") == 1234.56
    assert money_to_float("-10,00") == -10.0
    assert money_to_float("texto") is None


def test_classify_deduction_sign_and_subcategory() -> None:
    rules = get_normalized_subcategory_rules()
    categoria, subcategoria, importe = classify_entry("TRIBUTACION I.R.P.F.", None, 100.0, rules)
    assert categoria == "Devengo"
    assert subcategoria == "Impuestos (IRPF)"
    assert importe == -100.0


def test_classify_negative_devengo_as_devengo() -> None:
    rules = get_normalized_subcategory_rules()
    categoria, subcategoria, importe = classify_entry("RETRIB. FLEXIBLE", -10.0, None, rules)
    assert categoria == "Devengo"
    assert subcategoria == "Beneficio en Especie"
    assert importe == -10.0
