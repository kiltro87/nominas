from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from nominas_app.services.supabase_client import SupabaseClient


def get_runtime_config() -> dict:
    cfg_path = Path("config.json")
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    if "SUPABASE_URL" in st.secrets and "SUPABASE_SERVICE_ROLE_KEY" in st.secrets:
        return {
            "supabase_url": str(st.secrets["SUPABASE_URL"]),
            "supabase_service_role_key": str(st.secrets["SUPABASE_SERVICE_ROLE_KEY"]),
            "supabase_schema": str(st.secrets.get("SUPABASE_SCHEMA", "public")),
        }
    return {}


def load_nominas_from_sheet() -> pd.DataFrame:
    cfg = get_runtime_config()
    if not cfg:
        return pd.DataFrame()
    try:
        client = SupabaseClient(
            url=cfg["supabase_url"],
            service_role_key=cfg["supabase_service_role_key"],
            schema=cfg.get("supabase_schema", "public"),
        )
        rows = client.select("nominas", columns="*", order="año.asc,mes.asc,concepto.asc")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No se pudo cargar 'nominas' desde Supabase: {exc}")
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    columns = {
        "año": "Año",
        "mes": "Mes",
        "concepto": "Concepto",
        "importe": "Importe",
        "categoría": "Categoría",
        "subcategoría": "Subcategoría",
        "file_id": "file_id",
        "file_name": "file_name",
    }
    df = pd.DataFrame(rows).rename(columns=columns)
    required = ["Año", "Mes", "Concepto", "Importe", "Categoría", "Subcategoría", "file_id", "file_name"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df[required]

