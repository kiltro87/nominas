import argparse
import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

DEFAULT_SUBCATEGORY_RULES = [
    ("SALARIO BASE", "Ingreso Fijo"),
    ("PLUS CONVENIO", "Ingreso Fijo"),
    ("ANTIGUEDAD", "Ingreso Fijo"),
    ("PAGA EXTRA VERANO", "Ingreso Fijo"),
    ("PAGA EXTRA NAVIDAD", "Ingreso Fijo"),
    ("SALARIO EXTRANJERO 7.P", "Ingreso Fijo"),
    ("MEJ VOL ABSORB", "Ingreso Fijo"),
    ("CAR ALLOWANCE", "Ingreso Fijo"),
    ("TELETRABAJO", "Ingreso Fijo"),
    ("SPOT BONUS", "Ingreso Variable (Bonus)"),
    ("COMMISSIONS DEFERRED", "Ingreso Variable (Bonus)"),
    ("DIVIDEND PAY", "Ingreso Variable (Dividendos)"),
    ("ESPP GAIN", "Ingreso Variable (ESPP)"),
    ("RSU GAIN", "Ingreso Variable (RSU)"),
    ("STOCK OPTIONS", "Ingreso Variable (RSU)"),
    ("RETRIB. FLEXIBLE", "Beneficio en Especie"),
    ("VISION BIK", "Beneficio en Especie"),
    ("GIFT", "Beneficio en Especie"),
    ("TICKET RESTAURANT - NO IRPF", "Beneficio en Especie"),
    ("TICKET RESTAURANT - EXCESO", "Beneficio en Especie"),
    ("SEGURO MEDICO ESPECIE", "Beneficio en Especie"),
    ("SEG. MEDICO ESPECIE NO IRPF", "Beneficio en Especie"),
    ("SEGURO MEDICO ESPECIE NO IRPF", "Beneficio en Especie"),
    ("SEGURO VIDA", "Beneficio en Especie"),
    ("FITNESS REIMB.", "Beneficio en Especie"),
    ("TICKET TRANSPORTE - NO IRPF", "Beneficio en Especie"),
    ("SEGURO ACC. ESPECIE", "Beneficio en Especie"),
    ("TRIBUTACION I.R.P.F.", "Impuestos (IRPF)"),
    ("TRIBUTACION IRPF", "Impuestos (IRPF)"),
    ("TAX REFUND", "Impuestos (Ajustes)"),
    ("IMP. INGR. A. CTA. VALORES ESPECIE", "Impuestos (Ajustes)"),
    ("COTIZACION CONT.COMU", "Seguridad Social"),
    ("COTIZACION MEI", "Seguridad Social"),
    ("COTIZACION ADIC. SOLIDARIDAD", "Seguridad Social"),
    ("COTIZACION FORMACION", "Seguridad Social"),
    ("COTIZACION DESEMPLEO", "Seguridad Social"),
    ("PLAN PENSIONES - APORT EMPRESA", "Ahorro Jubilación"),
    ("APORT. EMPLEADO P. PENS.", "Ahorro Jubilación"),
    ("ESPP DEDUCCION", "Inversión Acciones (ESPP)"),
    ("-ESPP REFUND", "Inversión Acciones (ESPP)"),
    ("DCTO CONCEPTOS EN ESPECIE", "Ajuste Contable"),
    ("IMPM. INGR. A CTA. ESP. CG.", "Ajuste Contable"),
]


MONTH_MAP = {
    "ENE": 1,
    "ENERO": 1,
    "FEB": 2,
    "FEBRERO": 2,
    "MAR": 3,
    "MARZO": 3,
    "ABR": 4,
    "ABRIL": 4,
    "MAY": 5,
    "MAYO": 5,
    "JUN": 6,
    "JUNIO": 6,
    "JUL": 7,
    "JULIO": 7,
    "AGO": 8,
    "AGOSTO": 8,
    "SEP": 9,
    "SEPTIEMBRE": 9,
    "OCT": 10,
    "OCTUBRE": 10,
    "NOV": 11,
    "NOVIEMBRE": 11,
    "DIC": 12,
    "DICIEMBRE": 12,
}


@dataclass
class TableCoords:
    # Coordenadas inferidas con pdfplumber en tu PDF de ejemplo.
    # El script también las recalcula dinámicamente por página.
    header_top: float
    header_bottom: float
    concept_x0: float = 150.0
    concept_x1: float = 410.0
    dev_x0: float = 410.0
    dev_x1: float = 480.0
    ded_x0: float = 480.0
    ded_x1: float = 560.0
    body_top: float = 330.0
    body_bottom: float = 540.0


def money_to_float(value: str) -> Optional[float]:
    v = value.strip().replace("€", "")
    if not v:
        return None
    if not re.match(r"^-?[\d\.]+,\d{2}$", v):
        return None
    return float(v.replace(".", "").replace(",", "."))


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_key(s: str) -> str:
    normalized = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_only = ascii_only.upper()
    ascii_only = re.sub(r"[^A-Z0-9\\s\\./-]", " ", ascii_only)
    return re.sub(r"\s+", " ", ascii_only).strip()


def load_subcategory_rules() -> List[Tuple[str, str]]:
    config_path = Path(__file__).with_name("subcategorias.json")
    if not config_path.exists():
        return DEFAULT_SUBCATEGORY_RULES

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        rules: List[Tuple[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            match = str(item.get("match", "")).strip()
            subcategory = str(item.get("subcategory", "")).strip()
            if match and subcategory:
                rules.append((match, subcategory))
        return rules or DEFAULT_SUBCATEGORY_RULES
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SUBCATEGORY_RULES


def get_subcategory_rules_version() -> str:
    """Devuelve un hash corto para auditar cambios en reglas de clasificación."""
    config_path = Path(__file__).with_name("subcategorias.json")
    if config_path.exists():
        payload = config_path.read_bytes()
    else:
        payload = json.dumps(DEFAULT_SUBCATEGORY_RULES, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


@lru_cache(maxsize=1)
def get_normalized_subcategory_rules() -> Tuple[Tuple[str, str], ...]:
    """Normaliza una sola vez los tokens de matching para acelerar clasificación."""
    return tuple((normalize_key(token), subcategory) for token, subcategory in load_subcategory_rules())


def parse_period_from_text(text: str) -> Tuple[Optional[int], Optional[int], Dict[str, Optional[str]]]:
    # Caso 1: PERIODO tipo "MENS 01 DIC 25"
    m = re.search(r"MENS\s+\d{2}\s+([A-ZÁÉÍÓÚ]{3,10})\s+(\d{2,4})", text)
    if m:
        month_raw = m.group(1).upper()
        year_raw = m.group(2)
        month = MONTH_MAP.get(month_raw)
        year = int(year_raw)
        if year < 100:
            year += 2000
        return year, month, {"period_token": m.group(0), "date_token": None}

    # Caso 2: FECHA tipo "31 DICIEMBRE 2025"
    d = re.search(r"\b\d{1,2}\s+([A-ZÁÉÍÓÚ]{3,10})\s+(\d{4})\b", text)
    if d:
        month_raw = d.group(1).upper()
        month = MONTH_MAP.get(month_raw)
        year = int(d.group(2))
        return year, month, {"period_token": None, "date_token": d.group(0)}

    return None, None, {"period_token": None, "date_token": None}


def _cluster_rows(words: List[Dict[str, Any]], tolerance: float = 2.0) -> List[List[Dict[str, Any]]]:
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: (w["top"], w["x0"]))
    rows: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = [words_sorted[0]]
    for w in words_sorted[1:]:
        if abs(w["top"] - current[-1]["top"]) <= tolerance:
            current.append(w)
        else:
            rows.append(sorted(current, key=lambda x: x["x0"]))
            current = [w]
    rows.append(sorted(current, key=lambda x: x["x0"]))
    return rows


def _is_noise_concept(concept: str) -> bool:
    c = concept.upper()
    if not c:
        return True
    noisy = [
        "BASE S.S.",
        "DETERMINACIÓN",
        "CONCEPTO BASE",
        "LIQUIDO",
        "FECHA",
    ]
    return any(n in c for n in noisy)


def _clean_concept(raw: str) -> str:
    c = normalize_text(raw)
    c = re.sub(r"^\d+\s+", "", c)  # código de concepto
    c = c.lstrip("*").strip()
    return c


def _extract_table_coords(page: pdfplumber.page.Page) -> Optional[TableCoords]:
    words = page.extract_words(use_text_flow=True)
    header_candidates = [
        w
        for w in words
        if w["text"] in {"CONCEPTO", "DEVENGOS", "DEDUCCIONES"} and w["top"] < page.height * 0.6
    ]
    if not header_candidates:
        return None

    # El documento repite "CONCEPTO" más abajo; usamos el encabezado de la tabla principal.
    h = min(header_candidates, key=lambda x: x["top"])
    header_top = h["top"]
    header_bottom = h["bottom"]

    # Si existe "Sigue en siguiente hoja", el cuerpo termina justo antes.
    seguir = next((w for w in words if w["text"].startswith("Sigue")), None)
    if seguir:
        body_bottom = seguir["top"] - 2
    else:
        # Si no hay "Sigue...", termina antes del bloque "BASE S.S."
        candidate = [w for w in words if w["text"] == "BASE" and w["top"] > header_bottom + 120]
        body_bottom = (min(candidate, key=lambda x: x["top"])["top"] - 2) if candidate else page.height * 0.68

    return TableCoords(
        header_top=header_top,
        header_bottom=header_bottom,
        body_top=header_bottom + 2,
        body_bottom=body_bottom,
    )


def _extract_rows_from_page(page: pdfplumber.page.Page) -> List[Dict[str, Any]]:
    coords = _extract_table_coords(page)
    if not coords:
        return []

    crop = page.crop((40, coords.body_top, 565, coords.body_bottom))
    words = crop.extract_words(use_text_flow=True)
    rows = _cluster_rows(words)

    records: List[Dict[str, Any]] = []
    for row_words in rows:
        concept_tokens = [
            w["text"]
            for w in row_words
            if coords.concept_x0 <= w["x0"] < coords.concept_x1
        ]
        dev_tokens = [
            w["text"]
            for w in row_words
            if coords.dev_x0 <= w["x0"] < coords.dev_x1
        ]
        ded_tokens = [
            w["text"]
            for w in row_words
            if coords.ded_x0 <= w["x0"] < coords.ded_x1
        ]

        concept = _clean_concept(" ".join(concept_tokens))
        if _is_noise_concept(concept):
            continue

        dev_candidates = [money_to_float(t) for t in dev_tokens]
        ded_candidates = [money_to_float(t) for t in ded_tokens]
        dev_values = [x for x in dev_candidates if x is not None]
        ded_values = [x for x in ded_candidates if x is not None]

        dev = dev_values[-1] if dev_values else None
        ded = ded_values[-1] if ded_values else None

        if dev is None and ded is None:
            continue

        records.append(
            {
                "concepto": concept,
                "devengos": dev,
                "deducciones": ded,
                "page": page.page_number,
            }
        )

    return records


def _extract_liquido(text: str) -> Optional[float]:
    # Captura número después de "LIQUIDO A PERCIBIR"
    m = re.search(r"LIQUIDO A PERCIBIR\s+([\d\.]+,\d{2})", text, flags=re.MULTILINE)
    if m:
        return money_to_float(m.group(1))
    return None


def _match_subcategory(concept: str, rules: Tuple[Tuple[str, str], ...]) -> str:
    key = normalize_key(concept)
    for token, subcategory in rules:
        if token in key:
            return subcategory
    return "No clasificado"


def classify_entry(
    concept: str, dev: Optional[float], ded: Optional[float], rules: Tuple[Tuple[str, str], ...]
) -> Tuple[str, str, float]:
    subcategory = _match_subcategory(concept, rules)

    if ded is not None:
        return "Devengo", subcategory, -abs(ded)

    if dev is not None:
        if dev < 0:
            return "Devengo", subcategory, dev
        return "Ingreso", subcategory, dev

    return "Devengo", "No clasificado", 0.0


def extract_payroll(pdf_path: str) -> Dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el PDF: {pdf_path}")

    with pdfplumber.open(str(path)) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)

        year, month, period_meta = parse_period_from_text(full_text)
        liquido_pdf = _extract_liquido(full_text)

        all_rows: List[Dict[str, Any]] = []
        for page in pdf.pages:
            all_rows.extend(_extract_rows_from_page(page))

    subcategory_rules = get_normalized_subcategory_rules()
    sheet_rows: List[Dict[str, Any]] = []
    total_dev = 0.0
    total_ded = 0.0

    for r in all_rows:
        categoria, subcategoria, importe = classify_entry(
            r["concepto"], r["devengos"], r["deducciones"], subcategory_rules
        )
        if r["devengos"] is not None:
            total_dev += r["devengos"]
        if r["deducciones"] is not None:
            total_ded += r["deducciones"]

        sheet_rows.append(
            {
                "Año": year,
                "Mes": month,
                "Concepto": r["concepto"],
                "Importe": round(importe, 2),
                "Categoría": categoria,
                "Subcategoría": subcategoria,
            }
        )

    neto_calculado = round(total_dev - total_ded, 2)
    neto_pdf = round(liquido_pdf, 2) if liquido_pdf is not None else None
    validacion_ok = neto_pdf is not None and abs(neto_calculado - neto_pdf) < 0.01

    return {
        "archivo": str(path),
        "periodo": {
            "año": year,
            "mes": month,
            **period_meta,
        },
        "coordenadas_detectadas": {
            "header_top_aprox": 319.85,
            "columnas": {
                "concepto": [150.0, 410.0],
                "devengos": [410.0, 480.0],
                "deducciones": [480.0, 560.0],
            },
            "nota": "Las coordenadas se recalculan dinámicamente por página a partir del encabezado.",
        },
        "totales": {
            "total_devengado": round(total_dev, 2),
            "total_deducir": round(total_ded, 2),
            "neto_calculado": neto_calculado,
            "liquido_a_percibir_pdf": neto_pdf,
            "validacion_neto": validacion_ok,
        },
        "lineas": all_rows,
        "sheet_rows": sheet_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extractor de nóminas PDF a JSON")
    parser.add_argument("pdf", help="Ruta del PDF de nómina")
    parser.add_argument("--pretty", action="store_true", help="JSON con indentación")
    args = parser.parse_args()

    result = extract_payroll(args.pdf)
    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
