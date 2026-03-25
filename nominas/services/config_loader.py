from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from sheets_client import SheetsClient


def get_runtime_config() -> dict:
    cfg_path = Path("config.json")
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    if "GOOGLE_CREDENTIALS_JSON" in st.secrets and "SPREADSHEET_ID" in st.secrets:
        temp_creds = Path(tempfile.gettempdir()) / "streamlit_credentials.json"
        raw_secret: Any = st.secrets["GOOGLE_CREDENTIALS_JSON"]
        payload: dict[str, Any]
        if isinstance(raw_secret, Mapping):
            payload = dict(raw_secret)
        else:
            raw_text = str(raw_secret).strip()
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                pattern = r'("private_key"\s*:\s*")(.*?)(")'
                match = re.search(pattern, raw_text, flags=re.DOTALL)
                if not match:
                    raise
                raw_key = match.group(2).replace("\\n", "\n")
                escaped_key = raw_key.replace("\\", "\\\\").replace("\n", "\\n")
                fixed = raw_text[: match.start(2)] + escaped_key + raw_text[match.end(2) :]
                payload = json.loads(fixed)

        if "private_key" in payload and isinstance(payload["private_key"], str):
            payload["private_key"] = payload["private_key"].replace("\r\n", "\n")

        temp_creds.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return {
            "credentials_path": str(temp_creds),
            "spreadsheet_id": str(st.secrets["SPREADSHEET_ID"]),
        }
    return {}


def load_nominas_from_sheet() -> pd.DataFrame:
    cfg = get_runtime_config()
    if not cfg:
        return pd.DataFrame()
    try:
        client = SheetsClient(cfg["credentials_path"], cfg["spreadsheet_id"])
        values = client.get_all_values("Nominas")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo cargar 'Nominas' desde Google Sheets: {exc}")
        return pd.DataFrame()
    if len(values) < 2:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])

