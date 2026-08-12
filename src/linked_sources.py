from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection
from typing import Iterator

from src.db import get_connection
from src.import_export import (
    ImportPreviewError,
    build_import_preview,
    detect_file_type,
    import_general_entry_rows,
    import_template_entry_rows,
)


SUPPORTED_LINKED_SOURCE_MODES = {"general_entry", "template_aware"}


class LinkedSourceError(ValueError):
    """A controlled linked-source error suitable for a future UI."""


class _ConfirmedWriteError(RuntimeError):
    pass


@contextmanager
def _connection(connection: Connection | None = None) -> Iterator[Connection]:
    if connection is not None:
        yield connection
        return
    owned = get_connection()
    try:
        yield owned
    finally:
        owned.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_summary() -> dict:
    return {
        "total_rows": 0,
        "new_valid_count": 0,
        "invalid_count": 0,
        "duplicate_count": 0,
    }


def _error_preview(
    message: str,
    *,
    source_path: str = "",
    source_type: str = "",
    import_mode: str = "",
    sheet_name: str | None = None,
) -> dict:
    return {
        "ok": False,
        "can_confirm": False,
        "source_path": source_path,
        "source_type": source_type,
        "import_mode": import_mode,
        "sheet_name": sheet_name,
        "new_valid_rows": [],
        "invalid_rows": [],
        "duplicate_rows": [],
        "warnings": [],
        "errors": [message],
        "summary": _empty_summary(),
    }


def _normalized_source_path(source_path: str | Path) -> Path:
    value = str(source_path or "").strip()
    if not value:
        raise LinkedSourceError("Linked source is unavailable.")
    try:
        return Path(value).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise LinkedSourceError("Linked source is unavailable.") from error


def _controlled_preview_error(error: ImportPreviewError) -> str:
    message = str(error)
    if "Worksheet" in message:
        return "Worksheet is unavailable."
    if "Unsupported file format" in message or "Legacy .xls" in message:
        return "Linked source format is no longer supported."
    return "Linked source could not be read."


def _collection_exists(connection: Connection, collection_id: int) -> bool:
    return connection.execute(
        "SELECT 1 FROM collections WHERE id = ?",
        (int(collection_id),),
    ).fetchone() is not None


def _get_link(connection: Connection, collection_id: int) -> dict | None:
    row = connection.execute(
        """
        SELECT collection_id, source_path, source_type, import_mode,
               sheet_name, linked_at, last_refreshed_at
        FROM collection_source_links
        WHERE collection_id = ?
        """,
        (int(collection_id),),
    ).fetchone()
    return None if row is None else dict(row)


def get_collection_source_link(
    collection_id: int,
    connection: Connection | None = None,
) -> dict | None:
    with _connection(connection) as conn:
        return _get_link(conn, collection_id)


def _build_source_preview(
    connection: Connection,
    *,
    source_path: str | Path,
    import_mode: str,
    sheet_name: str | None,
    expected_source_type: str | None = None,
) -> dict:
    if import_mode not in SUPPORTED_LINKED_SOURCE_MODES:
        return _error_preview(
            "Linked source import mode is not supported.",
            import_mode=str(import_mode or ""),
            sheet_name=sheet_name,
        )

    try:
        path = _normalized_source_path(source_path)
    except LinkedSourceError as error:
        return _error_preview(
            str(error),
            import_mode=import_mode,
            sheet_name=sheet_name,
        )

    stored_path = str(path)
    try:
        source_type = detect_file_type(path.name)
    except ImportPreviewError as error:
        return _error_preview(
            _controlled_preview_error(error),
            source_path=stored_path,
            import_mode=import_mode,
            sheet_name=sheet_name,
        )

    if expected_source_type is not None and source_type != expected_source_type:
        return _error_preview(
            "Linked source format is no longer supported.",
            source_path=stored_path,
            source_type=source_type,
            import_mode=import_mode,
            sheet_name=sheet_name,
        )

    selected_sheet = str(sheet_name).strip() if source_type == "xlsx" and sheet_name else None
    try:
        file_bytes = path.read_bytes()
    except FileNotFoundError:
        return _error_preview(
            "Linked source is unavailable.",
            source_path=stored_path,
            source_type=source_type,
            import_mode=import_mode,
            sheet_name=selected_sheet,
        )
    except OSError:
        return _error_preview(
            "Linked source could not be read.",
            source_path=stored_path,
            source_type=source_type,
            import_mode=import_mode,
            sheet_name=selected_sheet,
        )

    try:
        preview = build_import_preview(
            file_bytes,
            path.name,
            mode=import_mode,
            options={"sheet_name": selected_sheet} if source_type == "xlsx" else {},
            connection=connection,
        )
    except ImportPreviewError as error:
        return _error_preview(
            _controlled_preview_error(error),
            source_path=stored_path,
            source_type=source_type,
            import_mode=import_mode,
            sheet_name=selected_sheet,
        )

    duplicate_rows = [
        row for row in preview["valid_rows"] if bool(row.get("duplicate_candidate"))
    ]
    new_valid_rows = [
        row for row in preview["valid_rows"] if not bool(row.get("duplicate_candidate"))
    ]
    invalid_rows = list(preview["invalid_rows"])
    return {
        "ok": True,
        "can_confirm": True,
        "source_path": stored_path,
        "source_type": source_type,
        "import_mode": import_mode,
        "sheet_name": selected_sheet,
        "new_valid_rows": new_valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_rows": duplicate_rows,
        "warnings": list(preview.get("warnings", [])),
        "errors": [],
        "summary": {
            "total_rows": int(preview["summary"]["total_rows"]),
            "new_valid_count": len(new_valid_rows),
            "invalid_count": len(invalid_rows),
            "duplicate_count": len(duplicate_rows),
        },
    }


def preview_collection_source_link(
    collection_id: int,
    source_path: str | Path,
    import_mode: str,
    sheet_name: str | None = None,
    connection: Connection | None = None,
) -> dict:
    with _connection(connection) as conn:
        if not _collection_exists(conn, collection_id):
            return _error_preview("Collection does not exist.", import_mode=import_mode)
        if _get_link(conn, collection_id) is not None:
            return _error_preview(
                "Collection already has a linked source. Unlink it before linking another file.",
                import_mode=import_mode,
            )
        return _build_source_preview(
            conn,
            source_path=source_path,
            import_mode=import_mode,
            sheet_name=sheet_name,
        )


def _ensure_transaction(connection: Connection) -> None:
    if not connection.in_transaction:
        connection.execute("BEGIN")


def _rollback_savepoint(connection: Connection, savepoint: str) -> None:
    connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
    connection.execute(f"RELEASE SAVEPOINT {savepoint}")


def _write_new_rows(
    connection: Connection,
    *,
    collection_id: int,
    import_mode: str,
    rows: list[dict],
) -> dict:
    writer = (
        import_general_entry_rows
        if import_mode == "general_entry"
        else import_template_entry_rows
    )
    result = writer(
        rows,
        duplicate_handling="skip",
        target_collection_id=int(collection_id),
        connection=connection,
    )
    expected = len(rows)
    if (
        int(result.get("failed_count", 0))
        or int(result.get("skipped_duplicate_count", 0))
        or int(result.get("imported_count", 0)) != expected
    ):
        raise _ConfirmedWriteError("Linked source changes could not be applied.")
    return result


def _confirmation_failure(preview: dict, message: str | None = None) -> dict:
    result = dict(preview)
    result.update(
        {
            "success": False,
            "linked": False,
            "refreshed": False,
            "imported_count": 0,
        }
    )
    if message:
        result["errors"] = [message]
    return result


def confirm_collection_source_link(
    collection_id: int,
    source_path: str | Path,
    import_mode: str,
    sheet_name: str | None = None,
    connection: Connection | None = None,
) -> dict:
    owns_connection = connection is None
    conn = connection or get_connection()
    savepoint = "linked_source_initial_confirm"
    try:
        _ensure_transaction(conn)
        conn.execute(f"SAVEPOINT {savepoint}")
        if not _collection_exists(conn, collection_id):
            preview = _error_preview("Collection does not exist.", import_mode=import_mode)
            _rollback_savepoint(conn, savepoint)
            return _confirmation_failure(preview)
        if _get_link(conn, collection_id) is not None:
            preview = _error_preview(
                "Collection already has a linked source. Unlink it before linking another file.",
                import_mode=import_mode,
            )
            _rollback_savepoint(conn, savepoint)
            return _confirmation_failure(preview)

        preview = _build_source_preview(
            conn,
            source_path=source_path,
            import_mode=import_mode,
            sheet_name=sheet_name,
        )
        if not preview["can_confirm"]:
            _rollback_savepoint(conn, savepoint)
            return _confirmation_failure(preview)

        write_result = _write_new_rows(
            conn,
            collection_id=collection_id,
            import_mode=import_mode,
            rows=preview["new_valid_rows"],
        ) if preview["new_valid_rows"] else {"imported_count": 0}
        linked_at = _utc_now()
        conn.execute(
            """
            INSERT INTO collection_source_links (
                collection_id, source_path, source_type, import_mode,
                sheet_name, linked_at, last_refreshed_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                int(collection_id),
                preview["source_path"],
                preview["source_type"],
                import_mode,
                preview["sheet_name"],
                linked_at,
            ),
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if owns_connection:
            conn.commit()
        result = dict(preview)
        result.update(
            {
                "success": True,
                "linked": True,
                "refreshed": False,
                "imported_count": int(write_result.get("imported_count", 0)),
                "link": {
                    "collection_id": int(collection_id),
                    "source_path": preview["source_path"],
                    "source_type": preview["source_type"],
                    "import_mode": import_mode,
                    "sheet_name": preview["sheet_name"],
                    "linked_at": linked_at,
                    "last_refreshed_at": None,
                },
            }
        )
        return result
    except Exception:
        try:
            _rollback_savepoint(conn, savepoint)
        except Exception:
            if owns_connection:
                conn.rollback()
        if owns_connection:
            conn.rollback()
        preview = _error_preview(
            "Linked source changes could not be applied.",
            import_mode=import_mode,
            sheet_name=sheet_name,
        )
        return _confirmation_failure(preview)
    finally:
        if owns_connection:
            conn.close()


def preview_linked_source_refresh(
    collection_id: int,
    connection: Connection | None = None,
) -> dict:
    with _connection(connection) as conn:
        link = _get_link(conn, collection_id)
        if link is None:
            return _error_preview("Collection has no linked source.")
        preview = _build_source_preview(
            conn,
            source_path=link["source_path"],
            import_mode=link["import_mode"],
            sheet_name=link["sheet_name"],
            expected_source_type=link["source_type"],
        )
        preview["link"] = link
        return preview


def confirm_linked_source_refresh(
    collection_id: int,
    connection: Connection | None = None,
) -> dict:
    owns_connection = connection is None
    conn = connection or get_connection()
    savepoint = "linked_source_refresh_confirm"
    try:
        _ensure_transaction(conn)
        conn.execute(f"SAVEPOINT {savepoint}")
        link = _get_link(conn, collection_id)
        if link is None:
            preview = _error_preview("Collection has no linked source.")
            _rollback_savepoint(conn, savepoint)
            return _confirmation_failure(preview)

        preview = _build_source_preview(
            conn,
            source_path=link["source_path"],
            import_mode=link["import_mode"],
            sheet_name=link["sheet_name"],
            expected_source_type=link["source_type"],
        )
        preview["link"] = link
        if not preview["can_confirm"]:
            _rollback_savepoint(conn, savepoint)
            return _confirmation_failure(preview)

        write_result = _write_new_rows(
            conn,
            collection_id=collection_id,
            import_mode=link["import_mode"],
            rows=preview["new_valid_rows"],
        ) if preview["new_valid_rows"] else {"imported_count": 0}
        refreshed_at = _utc_now()
        conn.execute(
            "UPDATE collection_source_links SET last_refreshed_at = ? WHERE collection_id = ?",
            (refreshed_at, int(collection_id)),
        )
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        if owns_connection:
            conn.commit()
        result = dict(preview)
        result.update(
            {
                "success": True,
                "linked": True,
                "refreshed": True,
                "imported_count": int(write_result.get("imported_count", 0)),
            }
        )
        result["link"] = {**link, "last_refreshed_at": refreshed_at}
        return result
    except Exception:
        try:
            _rollback_savepoint(conn, savepoint)
        except Exception:
            if owns_connection:
                conn.rollback()
        if owns_connection:
            conn.rollback()
        preview = _error_preview("Linked source refresh could not be applied.")
        return _confirmation_failure(preview)
    finally:
        if owns_connection:
            conn.close()


def unlink_collection_source(
    collection_id: int,
    connection: Connection | None = None,
) -> dict:
    owns_connection = connection is None
    conn = connection or get_connection()
    try:
        _ensure_transaction(conn)
        cursor = conn.execute(
            "DELETE FROM collection_source_links WHERE collection_id = ?",
            (int(collection_id),),
        )
        if owns_connection:
            conn.commit()
        if cursor.rowcount == 0:
            return {
                "success": False,
                "unlinked": False,
                "errors": ["Collection has no linked source."],
            }
        return {"success": True, "unlinked": True, "errors": []}
    except Exception:
        if owns_connection:
            conn.rollback()
        return {
            "success": False,
            "unlinked": False,
            "errors": ["Linked source could not be unlinked."],
        }
    finally:
        if owns_connection:
            conn.close()
