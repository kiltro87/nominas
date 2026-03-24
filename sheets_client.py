from __future__ import annotations

from typing import Any, Iterable, List, Sequence

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, credentials_path: str, spreadsheet_id: str) -> None:
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self.service = build("sheets", "v4", credentials=creds)
        self.spreadsheet_id = spreadsheet_id

    def ensure_sheet(self, sheet_name: str) -> None:
        metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        existing = {s["properties"]["title"] for s in metadata.get("sheets", [])}
        if sheet_name in existing:
            return

        body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}
        self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body).execute()

    def get_all_values(self, sheet_name: str) -> List[List[str]]:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=sheet_name)
            .execute()
        )
        return result.get("values", [])

    def append_rows(self, sheet_name: str, rows: Sequence[Sequence[Any]]) -> None:
        if not rows:
            return
        body = {"values": [list(r) for r in rows]}
        (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=sheet_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    def replace_sheet_values(self, sheet_name: str, rows: Sequence[Sequence[Any]]) -> None:
        body = {"values": [list(r) for r in rows]}
        (
            self.service.spreadsheets()
            .values()
            .clear(spreadsheetId=self.spreadsheet_id, range=sheet_name, body={})
            .execute()
        )
        if not rows:
            return
        (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body=body,
            )
            .execute()
        )


def ensure_header(client: SheetsClient, sheet_name: str, header: Iterable[str]) -> None:
    values = client.get_all_values(sheet_name)
    if values:
        return
    client.append_rows(sheet_name, [list(header)])
