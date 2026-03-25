from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from extractor import extract_payroll, get_subcategory_rules_version
from sheets_client import SheetsClient, ensure_header


DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

NOMINAS_SHEET = "Nominas"
CONTROL_SHEET = "Control"

NOMINAS_HEADER = ["Año", "Mes", "Concepto", "Importe", "Categoría", "Subcategoría", "file_id", "file_name"]
CONTROL_HEADER = [
    "file_id",
    "file_name",
    "md5_drive",
    "source_folder_breadcrumb",
    "renamed_to",
    "target_folder_breadcrumb",
    "rules_version",
    "processed_at_utc",
    "status",
    "error",
]

MONTH_NAMES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def load_config(config_path: str) -> Dict[str, str]:
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    required = ["credentials_path", "drive_folder_id", "spreadsheet_id"]
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Faltan claves en config: {', '.join(missing)}")
    return cfg


def build_drive_service(credentials_path: str):
    creds = Credentials.from_service_account_file(credentials_path, scopes=DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)


def list_pdf_files(drive_service, folder_id: str, modified_after: Optional[str] = None) -> List[Dict[str, Any]]:
    folders_to_visit: List[tuple[str, str]] = [(folder_id, "")]
    visited_folders: Set[str] = set()
    files: List[Dict[str, Any]] = []

    while folders_to_visit:
        current_folder, current_path = folders_to_visit.pop(0)
        if current_folder in visited_folders:
            continue
        visited_folders.add(current_folder)

        page_token = None
        while True:
            if modified_after:
                query = (
                    f"'{current_folder}' in parents and trashed=false and "
                    "("
                    "mimeType='application/vnd.google-apps.folder' or "
                    f"(mimeType='application/pdf' and modifiedTime > '{modified_after}')"
                    ")"
                )
            else:
                query = f"'{current_folder}' in parents and trashed=false"
            response = (
                drive_service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime)",
                    orderBy="modifiedTime desc",
                    pageSize=200,
                    pageToken=page_token,
                )
                .execute()
            )

            for item in response.get("files", []):
                mime_type = item.get("mimeType", "")
                if mime_type == "application/pdf":
                    item["source_folder_breadcrumb"] = current_path or "/"
                    files.append(item)
                elif mime_type == "application/vnd.google-apps.folder":
                    next_path = f"{current_path}/{item['name']}" if current_path else f"/{item['name']}"
                    folders_to_visit.append((item["id"], next_path))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

    files.sort(key=lambda x: x.get("modifiedTime", ""), reverse=True)
    return files


def should_skip_file(file_name: str) -> bool:
    return file_name.strip().lower().startswith("certificado")


def ensure_year_folder(drive_service, root_folder_id: str, year: int) -> str:
    folder_name = str(year)
    query = (
        f"'{root_folder_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{folder_name}' and trashed=false"
    )
    response = (
        drive_service.files()
        .list(q=query, fields="files(id, name)", pageSize=10)
        .execute()
    )
    matches = response.get("files", [])
    if matches:
        return matches[0]["id"]

    created = (
        drive_service.files()
        .create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [root_folder_id],
            },
            fields="id",
        )
        .execute()
    )
    return created["id"]


def build_payroll_filename(month: int | None, year: int | None, fallback_name: str) -> str:
    if year and month in MONTH_NAMES_ES:
        return f"Nómina {MONTH_NAMES_ES[month]} {year}.pdf"
    return fallback_name


def move_and_rename_file(
    drive_service,
    file_id: str,
    root_folder_id: str,
    target_year: int | None,
    target_name: str,
) -> None:
    if not target_year:
        return

    target_folder_id = ensure_year_folder(drive_service, root_folder_id, target_year)
    current = (
        drive_service.files()
        .get(fileId=file_id, fields="parents")
        .execute()
    )
    prev_parents = ",".join(current.get("parents", []))

    drive_service.files().update(
        fileId=file_id,
        addParents=target_folder_id,
        removeParents=prev_parents,
        body={"name": target_name},
        fields="id, parents, name",
    ).execute()


def download_file(drive_service, file_id: str, target_path: Path) -> None:
    request = drive_service.files().get_media(fileId=file_id)
    with target_path.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _extract_processed_registry(rows: List[List[str]]) -> Tuple[Set[str], Set[str]]:
    """Devuelve sets de file_id y md5 ya procesados desde la hoja Control."""
    if len(rows) <= 1:
        return set(), set()
    header = rows[0]
    idx_file = header.index("file_id") if "file_id" in header else 0
    idx_md5 = header.index("md5_drive") if "md5_drive" in header else -1
    processed_ids: Set[str] = set()
    processed_md5: Set[str] = set()
    for r in rows[1:]:
        if idx_file >= 0 and len(r) > idx_file and r[idx_file]:
            processed_ids.add(r[idx_file])
        if idx_md5 >= 0 and len(r) > idx_md5 and r[idx_md5]:
            processed_md5.add(r[idx_md5])
    return processed_ids, processed_md5


def _compute_modified_after(rows: List[List[str]], lookback_hours: int = 24) -> Optional[str]:
    if len(rows) <= 1:
        return None
    header = rows[0]
    if "processed_at_utc" not in header:
        return None
    idx_ts = header.index("processed_at_utc")
    latest: Optional[datetime] = None
    for r in rows[1:]:
        if len(r) <= idx_ts or not r[idx_ts]:
            continue
        raw = str(r[idx_ts]).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        if latest is None or parsed > latest:
            latest = parsed
    if latest is None:
        return None
    cutoff = latest - timedelta(hours=lookback_hours)
    return cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_processing_state(sheets: SheetsClient) -> Tuple[Set[str], Set[str], Optional[str]]:
    rows = sheets.get_all_values(CONTROL_SHEET)
    processed_ids, processed_md5 = _extract_processed_registry(rows)
    modified_after = _compute_modified_after(rows)
    return processed_ids, processed_md5, modified_after


def to_nominas_rows(sheet_rows: List[Dict[str, Any]], file_id: str, file_name: str) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for r in sheet_rows:
        rows.append(
            [
                r["Año"],
                r["Mes"],
                r["Concepto"],
                r["Importe"],
                r["Categoría"],
                r["Subcategoría"],
                file_id,
                file_name,
            ]
        )
    return rows


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_file_quality_alerts(result: Dict[str, Any]) -> List[str]:
    alerts: List[str] = []
    if not result.get("totales", {}).get("validacion_neto", False):
        alerts.append("Neto calculado no cuadra con LIQUIDO A PERCIBIR")
    concepts = [str(x.get("concepto", "")).upper() for x in result.get("lineas", [])]
    if not any("SALARIO BASE" in c for c in concepts):
        alerts.append("No se detectó concepto SALARIO BASE")
    return alerts


def process_new_payrolls(config_path: str, limit: int | None = None) -> Dict[str, Any]:
    cfg = load_config(config_path)
    credentials_path = cfg["credentials_path"]
    folder_id = cfg["drive_folder_id"]
    spreadsheet_id = cfg["spreadsheet_id"]

    drive = build_drive_service(credentials_path)
    sheets = SheetsClient(credentials_path, spreadsheet_id)
    sheets.ensure_sheet(NOMINAS_SHEET)
    sheets.ensure_sheet(CONTROL_SHEET)
    ensure_header(sheets, NOMINAS_SHEET, NOMINAS_HEADER)
    ensure_header(sheets, CONTROL_SHEET, CONTROL_HEADER)
    rules_version = get_subcategory_rules_version()

    processed_ids, processed_md5, modified_after = get_processing_state(sheets)
    files = list_pdf_files(drive, folder_id, modified_after=modified_after)

    processed = 0
    skipped = 0
    errors = 0
    details: List[Dict[str, Any]] = []

    for f in files:
        if limit is not None and processed >= limit:
            break

        file_id = f["id"]
        file_name = f.get("name", "")
        md5 = f.get("md5Checksum", "")

        if should_skip_file(file_name):
            skipped += 1
            continue

        if file_id in processed_ids or (md5 and md5 in processed_md5):
            skipped += 1
            continue

        status = "ok"
        error = ""
        source_breadcrumb = f.get("source_folder_breadcrumb", "/")
        renamed_to = file_name
        target_breadcrumb = source_breadcrumb
        quality_alerts: List[str] = []
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                temp_path = Path(tmp.name)
            download_file(drive, file_id, temp_path)

            result = extract_payroll(str(temp_path))
            quality_alerts = build_file_quality_alerts(result)
            nominas_rows = to_nominas_rows(result["sheet_rows"], file_id, file_name)
            sheets.append_rows(NOMINAS_SHEET, nominas_rows)
            period = result.get("periodo", {})
            year = period.get("año")
            month = period.get("mes")
            target_name = build_payroll_filename(month, year, file_name)
            move_and_rename_file(
                drive_service=drive,
                file_id=file_id,
                root_folder_id=folder_id,
                target_year=year,
                target_name=target_name,
            )
            renamed_to = target_name
            target_breadcrumb = f"/{year}" if year else source_breadcrumb
            processed += 1
            details.append(
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "source_folder_breadcrumb": source_breadcrumb,
                    "renamed_to": target_name,
                    "target_year_folder": year,
                    "target_folder_breadcrumb": target_breadcrumb,
                    "items": len(nominas_rows),
                    "validacion_neto": result["totales"]["validacion_neto"],
                    "quality_alerts": quality_alerts,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors += 1
            status = "error"
            error = str(exc)
            details.append({"file_id": file_id, "file_name": file_name, "error": error})
        finally:
            if "temp_path" in locals() and temp_path.exists():
                temp_path.unlink(missing_ok=True)

            sheets.append_rows(
                CONTROL_SHEET,
                [[
                    file_id,
                    file_name,
                    md5,
                    source_breadcrumb,
                    renamed_to,
                    target_breadcrumb,
                    rules_version,
                    now_utc(),
                    status,
                    "; ".join(quality_alerts + ([error] if error else [])),
                ]],
            )

    return {
        "processed": processed,
        "skipped_already_processed": skipped,
        "errors": errors,
        "total_drive_files_seen": len(files),
        "scan_modified_after": modified_after,
        "rules_version": rules_version,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta automática de nóminas desde Drive a Google Sheets")
    parser.add_argument("--config", default="config.json", help="Ruta al archivo config.json")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de PDFs a procesar en esta ejecución")
    args = parser.parse_args()

    summary = process_new_payrolls(args.config, args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
