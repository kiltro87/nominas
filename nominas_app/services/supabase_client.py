from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SupabaseClient:
    def __init__(self, url: str, service_role_key: str, schema: str = "public") -> None:
        self.url = url.rstrip("/")
        self.key = service_role_key
        self.schema = schema

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        qs = f"?{urlencode(params)}" if params else ""
        url = f"{self.url}{path}{qs}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = Request(url=url, data=data, method=method, headers=self._headers(headers))
        with urlopen(req) as resp:  # nosec B310 - trusted supabase endpoint
            raw = resp.read().decode("utf-8").strip()
            if not raw:
                return None
            return json.loads(raw)

    def select(
        self,
        table: str,
        columns: str = "*",
        filters: dict[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": columns}
        if filters:
            for k, v in filters.items():
                params[k] = f"eq.{v}"
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        out = self._request("GET", f"/rest/v1/{table}", params=params)
        return out if isinstance(out, list) else []

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._request(
            "POST",
            f"/rest/v1/{table}",
            body=rows,
            headers={"Prefer": "return=minimal"},
        )
