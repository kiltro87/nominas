from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from datetime import datetime

from nominas_app.services.supabase_client import SupabaseClient
from sheets_client import SheetsClient


def load_config(config_path: str) -> dict[str, str]:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    required = ["credentials_path", "spreadsheet_id", "supabase_url", "supabase_service_role_key"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Faltan claves en config: {', '.join(missing)}")
    return cfg


def parse_amount(value: Any) -> float:
    s = str(value).strip()
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if len(rows) < 2:
        return []
    header = rows[0]
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        item = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
        out.append(item)
    return out


def _is_timestamp(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def batched(items: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar datos de Google Sheets (Nominas/Control) a Supabase.")
    parser.add_argument("--config", default="config.json", help="Ruta a config.json")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar conteos sin escribir en Supabase")
    args = parser.parse_args()

    cfg = load_config(args.config)
    sheets = SheetsClient(cfg["credentials_path"], cfg["spreadsheet_id"])
    supabase = SupabaseClient(
        url=cfg["supabase_url"],
        service_role_key=cfg["supabase_service_role_key"],
        schema=cfg.get("supabase_schema", "public"),
    )

    nominas_rows_raw = rows_to_dicts(sheets.get_all_values("Nominas"))
    control_rows_raw = rows_to_dicts(sheets.get_all_values("Control"))

    existing_control = supabase.select("control", columns="file_id", order="processed_at_utc.asc", limit=100000)
    existing_ids = {str(r.get("file_id", "")).strip() for r in existing_control if r.get("file_id")}

    control_new_raw = [r for r in control_rows_raw if str(r.get("file_id", "")).strip() not in existing_ids]

    existing_nominas = supabase.select("nominas", columns="file_id")
    existing_nominas_ids = {str(r.get("file_id", "")).strip() for r in existing_nominas if r.get("file_id")}
    nominas_new_raw = [r for r in nominas_rows_raw if str(r.get("file_id", "")).strip() not in existing_nominas_ids]

    control_payload: list[dict[str, Any]] = []
    for r in control_new_raw:
        rules_version = str(r.get("rules_version", "")).strip() or None
        processed_at = str(r.get("processed_at_utc", "")).strip() or None
        status = str(r.get("status", "")).strip() or "ok"
        error = str(r.get("error", "")).strip() or None

        # Compatibilidad con histórico de Control sin columna rules_version:
        # [.., target_folder_breadcrumb, processed_at_utc(hash), status(timestamp), error(ok/error)]
        if rules_version is None and processed_at and not _is_timestamp(processed_at):
            candidate_rules = processed_at
            candidate_ts = status
            candidate_status = error
            rules_version = candidate_rules
            processed_at = candidate_ts if _is_timestamp(candidate_ts or "") else None
            status = candidate_status or "ok"
            error = None

        control_payload.append(
            {
                "file_id": str(r.get("file_id", "")).strip(),
                "file_name": str(r.get("file_name", "")).strip(),
                "md5_drive": str(r.get("md5_drive", "")).strip() or None,
                "source_folder_breadcrumb": str(r.get("source_folder_breadcrumb", "")).strip() or None,
                "renamed_to": str(r.get("renamed_to", "")).strip() or None,
                "target_folder_breadcrumb": str(r.get("target_folder_breadcrumb", "")).strip() or None,
                "rules_version": rules_version,
                "processed_at_utc": processed_at,
                "status": status,
                "error": error,
            }
        )

    nominas_payload: list[dict[str, Any]] = []
    skipped_invalid_period = 0
    for r in nominas_new_raw:
        year = int(float(str(r.get("Año", "0")).strip() or 0))
        month = int(float(str(r.get("Mes", "0")).strip() or 0))
        if year <= 0 or month < 1 or month > 12:
            skipped_invalid_period += 1
            continue
        nominas_payload.append(
            {
                "año": year,
                "mes": month,
                "concepto": str(r.get("Concepto", "")).strip(),
                "importe": parse_amount(r.get("Importe", 0)),
                "categoría": str(r.get("Categoría", "")).strip() or "Devengo",
                "subcategoría": str(r.get("Subcategoría", "")).strip() or "No clasificado",
                "file_id": str(r.get("file_id", "")).strip(),
                "file_name": str(r.get("file_name", "")).strip(),
            }
        )

    summary = {
        "sheet_nominas_total": len(nominas_rows_raw),
        "sheet_control_total": len(control_rows_raw),
        "supabase_control_existing": len(existing_ids),
        "supabase_nominas_existing_file_ids": len(existing_nominas_ids),
        "control_to_insert": len(control_payload),
        "nominas_to_insert": len(nominas_payload),
        "nominas_skipped_invalid_period": skipped_invalid_period,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.dry_run:
        return

    for batch in batched(control_payload, size=500):
        supabase.insert_rows("control", batch)
    for batch in batched(nominas_payload, size=1000):
        supabase.insert_rows("nominas", batch)

    print(json.dumps({"status": "ok", "inserted_control": len(control_payload), "inserted_nominas": len(nominas_payload)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
