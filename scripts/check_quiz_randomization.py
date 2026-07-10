from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import quiz  # noqa: E402


class NoOpRandom:
    def shuffle(self, items: list) -> None:
        return None

    def sample(self, items: list, count: int) -> list:
        return list(items)[:count]

    def choice(self, items: list):
        return list(items)[0]


def assert_not_equal(actual, unexpected, label: str) -> None:
    if actual == unexpected:
        raise AssertionError(f"{label} did not change order.")


def main() -> None:
    original_random = quiz._RANDOM
    try:
        quiz._RANDOM = NoOpRandom()

        original_values = [1, 2, 3, 4]
        shuffled_values = quiz.shuffle_sequence(original_values)
        assert_not_equal(shuffled_values, original_values, "shuffle_sequence fallback")

        options = quiz.shuffle_mcq_options("correct", ["wrong-a", "wrong-b", "wrong-c"])
        assert_not_equal(options, ["correct", "wrong-a", "wrong-b", "wrong-c"], "MCQ option shuffle fallback")
        if sorted(options) != sorted(["correct", "wrong-a", "wrong-b", "wrong-c"]):
            raise AssertionError("MCQ options changed their members.")

        entries = [
            {"id": 1, "term": "un", "meaning": "one"},
            {"id": 2, "term": "deux", "meaning": "two"},
            {"id": 3, "term": "trois", "meaning": "three"},
            {"id": 4, "term": "quatre", "meaning": "four"},
        ]
        quiz_items = quiz.create_quiz_items(entries, "term_to_meaning")
        generated_order = [item["entry_id"] for item in quiz_items]
        assert_not_equal(generated_order, [entry["id"] for entry in entries], "quiz item order fallback")
    finally:
        quiz._RANDOM = original_random

    print("Quiz randomization checks passed.")


if __name__ == "__main__":
    main()
