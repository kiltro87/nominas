from drive_ingestor import _compute_modified_after, _extract_processed_registry


def test_extract_processed_registry_reads_file_id_and_md5() -> None:
    rows = [
        [
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
        ],
        ["id_1", "a.pdf", "md5_a", "/", "a.pdf", "/2025", "v1", "ts", "ok", ""],
        ["id_2", "b.pdf", "md5_b", "/", "b.pdf", "/2025", "v1", "ts", "ok", ""],
    ]
    processed_ids, processed_md5 = _extract_processed_registry(rows)
    assert processed_ids == {"id_1", "id_2"}
    assert processed_md5 == {"md5_a", "md5_b"}


def test_extract_processed_registry_handles_missing_md5_column() -> None:
    rows = [
        ["file_id", "file_name", "status"],
        ["id_1", "a.pdf", "ok"],
    ]
    processed_ids, processed_md5 = _extract_processed_registry(rows)
    assert processed_ids == {"id_1"}
    assert processed_md5 == set()


def test_compute_modified_after_uses_latest_timestamp_minus_lookback() -> None:
    rows = [
        ["file_id", "processed_at_utc", "status"],
        ["id_1", "2026-03-24T08:00:00+00:00", "ok"],
        ["id_2", "2026-03-24T10:30:00Z", "ok"],
    ]
    cutoff = _compute_modified_after(rows, lookback_hours=24)
    assert cutoff == "2026-03-23T10:30:00Z"


def test_compute_modified_after_returns_none_without_valid_timestamps() -> None:
    rows = [
        ["file_id", "processed_at_utc", "status"],
        ["id_1", "", "ok"],
        ["id_2", "not-a-date", "ok"],
    ]
    assert _compute_modified_after(rows) is None
