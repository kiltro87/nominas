from drive_ingestor import _extract_processed_registry


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
