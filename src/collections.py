from datetime import datetime, timezone

from src.db import get_connection


SYSTEM_COLLECTION_TYPES = {
    "mistake_book": "Mistake Book",
    "starred": "Starred",
    "proficient_pool": "Proficient Pool",
}

COLLECTION_COLUMNS = """
    c.id,
    c.name,
    c.description,
    c.card_size,
    COALESCE(c.is_system, 0) AS is_system,
    c.system_type,
    c.created_at,
    c.updated_at,
    COUNT(ec.entry_id) AS entry_count
"""

ENTRY_IN_COLLECTION_COLUMNS = """
    e.id,
    e.template_id,
    COALESCE(t.name, '') AS template_name,
    COALESCE(t.template_type, '') AS template_type,
    e.language,
    e.explanation_language,
    e.entry_type,
    e.term,
    e.meaning,
    e.example,
    e.notes,
    e.tags,
    e.source,
    e.status,
    e.created_at,
    e.updated_at,
    ec.position,
    ec.added_at
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_card_size(card_size: int) -> None:
    if card_size < 1:
        raise ValueError("card_size must be at least 1")


def create_collection(name: str, description: str = "", card_size: int = 8) -> int:
    clean_name = name.strip()
    clean_description = description.strip()
    _validate_card_size(card_size)

    if not clean_name:
        raise ValueError("Collection name is required")

    now = _now_iso()

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO collections (
                    name,
                    description,
                    card_size,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_name, clean_description, card_size, now, now),
            )
            return int(cursor.lastrowid)
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            raise ValueError(f"Collection already exists: {clean_name}") from error
        raise


def update_collection(
    collection_id: int,
    name: str,
    description: str,
    card_size: int,
) -> None:
    clean_name = name.strip()
    clean_description = description.strip()
    _validate_card_size(card_size)

    if not clean_name:
        raise ValueError("Collection name is required")

    now = _now_iso()

    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE collections
                SET
                    name = ?,
                    description = ?,
                    card_size = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (clean_name, clean_description, card_size, now, collection_id),
            )
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            raise ValueError(f"Collection already exists: {clean_name}") from error
        raise



def delete_collection(collection_id: int) -> dict:
    with get_connection() as connection:
        collection = connection.execute(
            """
            SELECT id, name, COALESCE(is_system, 0) AS is_system, system_type
            FROM collections
            WHERE id = ?
            """,
            (int(collection_id),),
        ).fetchone()
        if collection is None:
            raise ValueError("Collection not found.")
        if collection["is_system"]:
            raise ValueError("System collections cannot be deleted.")

        detached_entries = int(
            connection.execute(
                "SELECT COUNT(*) FROM entry_collections WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]
        )
        review_states = int(
            connection.execute(
                "SELECT COUNT(*) FROM card_review_states WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]
        )
        review_logs = int(
            connection.execute(
                "SELECT COUNT(*) FROM card_review_logs WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]
        )
        quiz_sessions = int(
            connection.execute(
                "SELECT COUNT(*) FROM quiz_sessions WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]
        )
        card_metadata = int(
            connection.execute(
                "SELECT COUNT(*) FROM collection_card_metadata WHERE collection_id = ?",
                (int(collection_id),),
            ).fetchone()[0]
        )

        connection.execute("DELETE FROM quiz_sessions WHERE collection_id = ?", (int(collection_id),))
        connection.execute("DELETE FROM card_review_logs WHERE collection_id = ?", (int(collection_id),))
        connection.execute("DELETE FROM card_review_states WHERE collection_id = ?", (int(collection_id),))
        connection.execute("DELETE FROM collection_card_metadata WHERE collection_id = ?", (int(collection_id),))
        connection.execute("DELETE FROM entry_collections WHERE collection_id = ?", (int(collection_id),))
        cursor = connection.execute("DELETE FROM collections WHERE id = ?", (int(collection_id),))
        if cursor.rowcount != 1:
            raise ValueError("Collection could not be deleted.")

    return {
        "deleted": True,
        "collection_id": int(collection_id),
        "collection_name": collection["name"],
        "detached_entry_count": detached_entries,
        "deleted_review_state_count": review_states,
        "deleted_review_log_count": review_logs,
        "deleted_quiz_session_count": quiz_sessions,
        "deleted_card_metadata_count": card_metadata,
    }


def get_collections() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {COLLECTION_COLUMNS}
            FROM collections c
            LEFT JOIN entry_collections ec ON ec.collection_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC, c.id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_collection_by_name(name: str) -> dict | None:
    clean_name = name.strip()

    if not clean_name:
        return None

    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {COLLECTION_COLUMNS}
            FROM collections c
            LEFT JOIN entry_collections ec ON ec.collection_id = c.id
            WHERE c.name = ?
            GROUP BY c.id
            """,
            (clean_name,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_collection_by_id(collection_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {COLLECTION_COLUMNS}
            FROM collections c
            LEFT JOIN entry_collections ec ON ec.collection_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (collection_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_system_collection(system_type: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            f"""
            SELECT {COLLECTION_COLUMNS}
            FROM collections c
            LEFT JOIN entry_collections ec ON ec.collection_id = c.id
            WHERE c.system_type = ?
            GROUP BY c.id
            """,
            (system_type,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def get_system_collection_by_type_or_name(system_type: str) -> dict | None:
    system_collection = get_system_collection(system_type)
    if system_collection is not None:
        return system_collection

    fallback_name = SYSTEM_COLLECTION_TYPES.get(system_type)
    if fallback_name is None:
        return None

    return get_collection_by_name(fallback_name)


def get_or_create_collection_by_name(
    name: str,
    description: str = "",
    card_size: int = 8,
) -> int:
    existing_collection = get_collection_by_name(name)

    if existing_collection is not None:
        return int(existing_collection["id"])

    return create_collection(name, description, card_size)


def get_or_create_system_collection(
    system_type: str,
    name: str,
    description: str = "",
    card_size: int = 8,
) -> int:
    clean_system_type = system_type.strip()
    clean_name = name.strip()
    clean_description = description.strip()
    _validate_card_size(card_size)

    if not clean_system_type:
        raise ValueError("system_type is required")

    if not clean_name:
        raise ValueError("Collection name is required")

    existing_system_collection = get_system_collection(clean_system_type)
    if existing_system_collection is not None:
        return int(existing_system_collection["id"])

    existing_named_collection = get_collection_by_name(clean_name)
    now = _now_iso()

    if existing_named_collection is not None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE collections
                SET
                    is_system = 1,
                    system_type = ?,
                    description = CASE
                        WHEN COALESCE(description, '') = '' THEN ?
                        ELSE description
                    END,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    clean_system_type,
                    clean_description,
                    now,
                    existing_named_collection["id"],
                ),
            )
        return int(existing_named_collection["id"])

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO collections (
                name,
                description,
                card_size,
                is_system,
                system_type,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (clean_name, clean_description, card_size, clean_system_type, now, now),
        )

    return int(cursor.lastrowid)


def add_entries_to_collection(entry_ids: list[int], collection_id: int) -> int:
    unique_entry_ids = list(dict.fromkeys(entry_ids))

    if not unique_entry_ids:
        return 0

    now = _now_iso()

    with get_connection() as connection:
        existing_rows = connection.execute(
            f"""
            SELECT entry_id
            FROM entry_collections
            WHERE collection_id = ?
              AND entry_id IN ({','.join('?' for _ in unique_entry_ids)})
            """,
            (collection_id, *unique_entry_ids),
        ).fetchall()
        existing_entry_ids = {row["entry_id"] for row in existing_rows}
        new_entry_ids = [
            entry_id for entry_id in unique_entry_ids if entry_id not in existing_entry_ids
        ]

        if not new_entry_ids:
            return 0

        max_position = connection.execute(
            """
            SELECT COALESCE(MAX(position), 0)
            FROM entry_collections
            WHERE collection_id = ?
            """,
            (collection_id,),
        ).fetchone()[0]

        rows_to_insert = [
            (entry_id, collection_id, max_position + index, now)
            for index, entry_id in enumerate(new_entry_ids, start=1)
        ]
        cursor = connection.executemany(
            """
            INSERT INTO entry_collections (
                entry_id,
                collection_id,
                position,
                added_at
            )
            VALUES (?, ?, ?, ?)
            """,
            rows_to_insert,
        )

    return cursor.rowcount


def add_entries_to_system_collection(entry_ids: list[int], system_type: str) -> int:
    collection_name = SYSTEM_COLLECTION_TYPES.get(system_type, system_type)
    collection_id = get_or_create_system_collection(
        system_type,
        collection_name,
        f"System collection for {collection_name}.",
        8,
    )
    return add_entries_to_collection(entry_ids, collection_id)


def remove_entries_from_system_collection(entry_ids: list[int], system_type: str) -> int:
    system_collection = get_system_collection_by_type_or_name(system_type)

    if system_collection is None:
        return 0

    return remove_entries_from_collection(entry_ids, system_collection["id"])


def is_entry_in_system_collection(entry_id: int, system_type: str) -> bool:
    system_collection = get_system_collection_by_type_or_name(system_type)

    if system_collection is None:
        return False

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM entry_collections
            WHERE entry_id = ?
              AND collection_id = ?
            LIMIT 1
            """,
            (entry_id, system_collection["id"]),
        ).fetchone()

    return row is not None


def resolve_collection_names(collection_names: list[str]) -> tuple[list[dict], list[str]]:
    resolved_collections = []
    missing_names = []

    for collection_name in list(dict.fromkeys(collection_names)):
        collection = get_collection_by_name(collection_name)
        if collection is None:
            missing_names.append(collection_name)
        else:
            resolved_collections.append(collection)

    return resolved_collections, missing_names


def add_entry_to_collections(entry_id: int, collection_ids: list[int]) -> dict:
    unique_collection_ids = list(dict.fromkeys(collection_ids))
    added_by_collection_id = {}

    for collection_id in unique_collection_ids:
        added_by_collection_id[collection_id] = add_entries_to_collection(
            [entry_id],
            collection_id,
        )

    return {
        "requested_count": len(collection_ids),
        "unique_count": len(unique_collection_ids),
        "added_count": sum(added_by_collection_id.values()),
        "added_by_collection_id": added_by_collection_id,
    }


def get_collection_ids_for_entry(entry_id: int) -> list[int]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT collection_id
            FROM entry_collections
            WHERE entry_id = ?
            ORDER BY collection_id ASC
            """,
            (int(entry_id),),
        ).fetchall()

    return [int(row["collection_id"]) for row in rows]


def update_entry_collections(
    entry_id: int,
    desired_collection_ids: list[int],
    managed_collection_ids: list[int] | None = None,
) -> dict:
    desired_ids = set(int(collection_id) for collection_id in desired_collection_ids)
    current_ids = set(get_collection_ids_for_entry(entry_id))
    managed_ids = (
        set(int(collection_id) for collection_id in managed_collection_ids)
        if managed_collection_ids is not None
        else current_ids | desired_ids
    )

    add_ids = sorted(desired_ids - current_ids)
    remove_ids = sorted((current_ids - desired_ids) & managed_ids)

    added_count = 0
    for collection_id in add_ids:
        added_count += add_entries_to_collection([int(entry_id)], collection_id)

    removed_count = 0
    for collection_id in remove_ids:
        removed_count += remove_entries_from_collection([int(entry_id)], collection_id)

    return {
        "entry_id": int(entry_id),
        "requested_count": len(desired_ids),
        "added_count": added_count,
        "removed_count": removed_count,
        "final_collection_ids": sorted(desired_ids | (current_ids - managed_ids)),
    }


def get_entries_in_collection(collection_id: int) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {ENTRY_IN_COLLECTION_COLUMNS}
            FROM entry_collections ec
            JOIN entries e ON e.id = ec.entry_id
            LEFT JOIN entry_templates t ON t.id = e.template_id
            WHERE ec.collection_id = ?
            ORDER BY ec.position ASC, ec.id ASC
            """,
            (collection_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_entries_in_system_collection(system_type: str) -> list[dict]:
    system_collection = get_system_collection_by_type_or_name(system_type)

    if system_collection is None:
        return []

    return get_entries_in_collection(system_collection["id"])


def get_entries_in_special_collection_filtered(
    system_type: str,
    related_collection_id: int | None = None,
) -> list[dict]:
    system_collection = get_system_collection_by_type_or_name(system_type)

    if system_collection is None:
        return []

    params = [system_collection["id"]]
    related_join_sql = ""
    related_where_sql = ""

    if related_collection_id is not None:
        related_join_sql = """
            JOIN entry_collections related_ec
              ON related_ec.entry_id = e.id
        """
        related_where_sql = "AND related_ec.collection_id = ?"
        params.append(related_collection_id)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT {ENTRY_IN_COLLECTION_COLUMNS}
            FROM entry_collections ec
            JOIN entries e ON e.id = ec.entry_id
            LEFT JOIN entry_templates t ON t.id = e.template_id
            {related_join_sql}
            WHERE ec.collection_id = ?
              {related_where_sql}
            ORDER BY ec.position ASC, ec.id ASC
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_card_groups_for_collection(collection_id: int) -> list[dict]:
    collection = get_collection_by_id(collection_id)

    if collection is None:
        return []

    card_size = collection["card_size"]
    entries = get_entries_in_collection(collection_id)
    grouped_entries: dict[int, list[dict]] = {}

    for entry in entries:
        card_number = ((entry["position"] - 1) // card_size) + 1
        grouped_entries.setdefault(card_number, []).append(entry)

    card_metadata = get_card_metadata_for_collection(collection_id)

    return [
        {
            "card_number": card_number,
            "card_name": card_metadata.get(card_number, {}).get("name", ""),
            "card_created_at": card_metadata.get(card_number, {}).get("created_at", ""),
            "card_updated_at": card_metadata.get(card_number, {}).get("updated_at", ""),
            "entries": card_entries,
        }
        for card_number, card_entries in sorted(grouped_entries.items())
    ]


def get_card_names_for_collection(collection_id: int) -> dict[int, str]:
    return {
        card_number: metadata["name"]
        for card_number, metadata in get_card_metadata_for_collection(collection_id).items()
    }


def get_card_metadata_for_collection(collection_id: int) -> dict[int, dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                card_number,
                COALESCE(name, '') AS name,
                created_at,
                updated_at
            FROM collection_card_metadata
            WHERE collection_id = ?
            ORDER BY card_number ASC
            """,
            (int(collection_id),),
        ).fetchall()

    return {
        int(row["card_number"]): {
            "name": str(row["name"] or ""),
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
        }
        for row in rows
        if str(row["name"] or "").strip()
    }


def set_card_name(collection_id: int, card_number: int, name: str) -> None:
    if card_number < 1:
        raise ValueError("card_number must be at least 1")

    clean_name = str(name or "").strip()
    now = _now_iso()
    with get_connection() as connection:
        if clean_name:
            connection.execute(
                """
                INSERT INTO collection_card_metadata (
                    collection_id,
                    card_number,
                    name,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(collection_id, card_number) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at
                """,
                (int(collection_id), int(card_number), clean_name, now, now),
            )
        else:
            connection.execute(
                """
                DELETE FROM collection_card_metadata
                WHERE collection_id = ?
                  AND card_number = ?
                """,
                (int(collection_id), int(card_number)),
            )


def search_cards_by_name(search_text: str) -> list[dict]:
    clean_search = str(search_text or "").strip()
    if not clean_search:
        return []

    pattern = f"%{clean_search.lower()}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                metadata.collection_id,
                collections.name AS collection_name,
                metadata.card_number,
                metadata.name AS card_name,
                collections.card_size,
                COUNT(entry_collections.entry_id) AS entry_count
            FROM collection_card_metadata AS metadata
            JOIN collections ON collections.id = metadata.collection_id
            LEFT JOIN entry_collections
              ON entry_collections.collection_id = metadata.collection_id
             AND CAST((entry_collections.position - 1) / collections.card_size AS INTEGER) + 1 = metadata.card_number
            WHERE LOWER(COALESCE(metadata.name, '')) LIKE ?
            GROUP BY metadata.collection_id, metadata.card_number
            ORDER BY collections.name COLLATE NOCASE, metadata.card_number
            """,
            (pattern,),
        ).fetchall()

    return [dict(row) for row in rows]


def remove_entries_from_collection(entry_ids: list[int], collection_id: int) -> int:
    unique_entry_ids = list(dict.fromkeys(entry_ids))

    if not unique_entry_ids:
        return 0

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            DELETE FROM entry_collections
            WHERE collection_id = ?
              AND entry_id IN ({','.join('?' for _ in unique_entry_ids)})
            """,
            (collection_id, *unique_entry_ids),
        )
        deleted_count = cursor.rowcount

    normalize_collection_positions(collection_id)
    return deleted_count


def move_entry_in_collection(
    collection_id: int,
    entry_id: int,
    new_position: int,
) -> None:
    entries = get_entries_in_collection(collection_id)
    entry_ids = [entry["id"] for entry in entries]

    if entry_id not in entry_ids:
        raise ValueError("Entry is not in the selected collection")

    if new_position < 1 or new_position > len(entry_ids):
        raise ValueError(
            f"new_position must be between 1 and {len(entry_ids)} for this collection"
        )

    entry_ids.remove(entry_id)
    entry_ids.insert(new_position - 1, entry_id)

    with get_connection() as connection:
        connection.executemany(
            """
            UPDATE entry_collections
            SET position = ?
            WHERE collection_id = ?
              AND entry_id = ?
            """,
            [
                (position, collection_id, current_entry_id)
                for position, current_entry_id in enumerate(entry_ids, start=1)
            ],
        )


def normalize_collection_positions(collection_id: int) -> None:
    entries = get_entries_in_collection(collection_id)

    with get_connection() as connection:
        connection.executemany(
            """
            UPDATE entry_collections
            SET position = ?
            WHERE collection_id = ?
              AND entry_id = ?
            """,
            [
                (position, collection_id, entry["id"])
                for position, entry in enumerate(entries, start=1)
            ],
        )
