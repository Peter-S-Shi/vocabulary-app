from __future__ import annotations

from datetime import datetime, timezone
import sqlite3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ordered_entry_ids(conn: sqlite3.Connection, collection_id: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT entry_id
        FROM entry_collections
        WHERE collection_id = ?
        ORDER BY position ASC, id ASC
        """,
        (int(collection_id),),
    ).fetchall()
    return [int(row["entry_id"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows]


def _card_size(conn: sqlite3.Connection, collection_id: int) -> int:
    row = conn.execute(
        "SELECT card_size FROM collections WHERE id = ?",
        (int(collection_id),),
    ).fetchone()
    if row is None:
        raise ValueError("Collection not found.")
    value = row["card_size"] if isinstance(row, sqlite3.Row) else row[0]
    return max(int(value), 1)


def group_entry_ids(entry_ids: list[int], card_size: int) -> dict[int, list[int]]:
    if card_size < 1:
        raise ValueError("card_size must be at least 1")
    return {
        index // card_size + 1: entry_ids[index : index + card_size]
        for index in range(0, len(entry_ids), card_size)
    }


def detect_cross_card_moves(
    before_entry_ids: list[int],
    before_card_size: int,
    after_entry_ids: list[int],
    after_card_size: int,
) -> list[dict]:
    before_positions = {
        entry_id: index // before_card_size + 1
        for index, entry_id in enumerate(before_entry_ids)
    }
    after_positions = {
        entry_id: index // after_card_size + 1
        for index, entry_id in enumerate(after_entry_ids)
    }
    return [
        {
            "entry_id": entry_id,
            "from_card_number": before_positions[entry_id],
            "to_card_number": after_positions[entry_id],
        }
        for entry_id in before_entry_ids
        if entry_id in after_positions
        and before_positions[entry_id] != after_positions[entry_id]
    ]


def preview_collection_transition(
    conn: sqlite3.Connection,
    collection_id: int,
    *,
    proposed_entry_ids: list[int] | None = None,
    proposed_card_size: int | None = None,
) -> dict:
    before_entry_ids = _ordered_entry_ids(conn, collection_id)
    before_card_size = _card_size(conn, collection_id)
    after_entry_ids = list(before_entry_ids if proposed_entry_ids is None else proposed_entry_ids)
    after_card_size = before_card_size if proposed_card_size is None else int(proposed_card_size)
    moves = detect_cross_card_moves(
        before_entry_ids,
        before_card_size,
        after_entry_ids,
        after_card_size,
    )
    return {
        "collection_id": int(collection_id),
        "before_entry_ids": before_entry_ids,
        "after_entry_ids": after_entry_ids,
        "before_card_size": before_card_size,
        "after_card_size": after_card_size,
        "cross_card_moves": moves,
        "requires_confirmation": bool(moves),
    }


def _latest_revision(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, revision_number
        FROM card_revisions
        WHERE card_id = ?
        ORDER BY revision_number DESC
        LIMIT 1
        """,
        (int(card_id),),
    ).fetchone()


def _revision_entry_ids(conn: sqlite3.Connection, revision_id: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT entry_id
        FROM card_revision_entries
        WHERE revision_id = ?
        ORDER BY position_within_card ASC
        """,
        (int(revision_id),),
    ).fetchall()
    return [int(row["entry_id"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows]


def reconcile_collection_card_history(
    conn: sqlite3.Connection,
    collection_id: int,
    *,
    change_reason: str,
    migrate_legacy_names: bool = False,
) -> dict:
    now = _now_iso()
    current_groups = group_entry_ids(
        _ordered_entry_ids(conn, collection_id),
        _card_size(conn, collection_id),
    )
    active_rows = conn.execute(
        """
        SELECT id, card_number
        FROM cards
        WHERE collection_id = ? AND is_active = 1
        ORDER BY card_number
        """,
        (int(collection_id),),
    ).fetchall()
    active_by_number = {int(row["card_number"]): row for row in active_rows}
    created_card_ids: list[int] = []
    retired_card_ids: list[int] = []
    created_revision_ids: list[int] = []
    unchanged_card_ids: list[int] = []

    for card_number, entry_ids in current_groups.items():
        card_row = active_by_number.get(card_number)
        if card_row is None:
            legacy_name = ""
            if migrate_legacy_names:
                metadata = conn.execute(
                    """
                    SELECT COALESCE(name, '') AS name
                    FROM collection_card_metadata
                    WHERE collection_id = ? AND card_number = ?
                    """,
                    (int(collection_id), int(card_number)),
                ).fetchone()
                if metadata is not None:
                    legacy_name = str(metadata["name"] or "")
            cursor = conn.execute(
                """
                INSERT INTO cards (
                    collection_id, card_number, name, is_active,
                    created_at, updated_at, retired_at
                ) VALUES (?, ?, ?, 1, ?, ?, NULL)
                """,
                (int(collection_id), int(card_number), legacy_name, now, now),
            )
            card_id = int(cursor.lastrowid)
            created_card_ids.append(card_id)
        else:
            card_id = int(card_row["id"])
            conn.execute(
                "UPDATE cards SET card_number = ?, updated_at = ? WHERE id = ?",
                (int(card_number), now, card_id),
            )

        latest = _latest_revision(conn, card_id)
        latest_entry_ids = [] if latest is None else _revision_entry_ids(conn, int(latest["id"]))
        if latest is not None and latest_entry_ids == entry_ids:
            unchanged_card_ids.append(card_id)
            continue

        revision_number = 1 if latest is None else int(latest["revision_number"]) + 1
        cursor = conn.execute(
            """
            INSERT INTO card_revisions (card_id, revision_number, created_at, change_reason)
            VALUES (?, ?, ?, ?)
            """,
            (card_id, revision_number, now, str(change_reason or "membership_change")),
        )
        revision_id = int(cursor.lastrowid)
        conn.executemany(
            """
            INSERT INTO card_revision_entries (revision_id, entry_id, position_within_card)
            VALUES (?, ?, ?)
            """,
            [
                (revision_id, entry_id, position)
                for position, entry_id in enumerate(entry_ids, start=1)
            ],
        )
        created_revision_ids.append(revision_id)

    current_numbers = set(current_groups)
    for card_number, card_row in active_by_number.items():
        if card_number in current_numbers:
            continue
        card_id = int(card_row["id"])
        conn.execute(
            """
            UPDATE cards
            SET is_active = 0, retired_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, card_id),
        )
        retired_card_ids.append(card_id)

    return {
        "collection_id": int(collection_id),
        "created_card_ids": created_card_ids,
        "retired_card_ids": retired_card_ids,
        "created_revision_ids": created_revision_ids,
        "unchanged_card_ids": unchanged_card_ids,
    }


def get_current_card_identity(
    conn: sqlite3.Connection, collection_id: int, card_number: int
) -> dict | None:
    row = conn.execute(
        """
        SELECT
            cards.id AS card_id,
            cards.collection_id,
            cards.card_number,
            cards.name,
            revisions.id AS card_revision_id,
            revisions.revision_number
        FROM cards
        JOIN card_revisions AS revisions
          ON revisions.card_id = cards.id
        WHERE cards.collection_id = ?
          AND cards.card_number = ?
          AND cards.is_active = 1
          AND revisions.revision_number = (
              SELECT MAX(latest.revision_number)
              FROM card_revisions AS latest
              WHERE latest.card_id = cards.id
          )
        """,
        (int(collection_id), int(card_number)),
    ).fetchone()
    return None if row is None else dict(row)


def get_card_revision_entry_ids(conn: sqlite3.Connection, revision_id: int) -> list[int]:
    return _revision_entry_ids(conn, revision_id)


def get_quiz_session_card_revision(conn: sqlite3.Connection, session_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT id AS session_id, collection_id, card_number, card_id, card_revision_id
        FROM quiz_sessions
        WHERE id = ?
        """,
        (int(session_id),),
    ).fetchone()
    return None if row is None else dict(row)


def get_entry_card_revision_history(conn: sqlite3.Connection, entry_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            cards.id AS card_id,
            cards.collection_id,
            revisions.id AS card_revision_id,
            revisions.revision_number,
            revisions.created_at,
            membership.position_within_card
        FROM card_revision_entries AS membership
        JOIN card_revisions AS revisions ON revisions.id = membership.revision_id
        JOIN cards ON cards.id = revisions.card_id
        WHERE membership.entry_id = ?
        ORDER BY revisions.created_at, revisions.id
        """,
        (int(entry_id),),
    ).fetchall()
    return [dict(row) for row in rows]
