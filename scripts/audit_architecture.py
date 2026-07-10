from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
UI_DIR = SRC_DIR / "ui_streamlit"


def _is_ui_file(path: Path) -> bool:
    return path == PROJECT_ROOT / "app.py" or UI_DIR in path.parents


def _module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return ",".join(alias.name for alias in node.names)


def _looks_like_sql(value: str) -> bool:
    if "\n" not in value:
        return False
    normalized = " ".join(value.upper().split())
    statements = (
        ("SELECT ", " FROM "),
        ("INSERT ", " INTO "),
        ("UPDATE ", " SET "),
        ("DELETE ", " FROM "),
        ("CREATE ", " TABLE "),
        ("ALTER ", " TABLE "),
    )
    return any(
        normalized.startswith(first) and second in normalized
        for first, second in statements
    )


def audit_file(path: Path) -> tuple[list[str], list[str]]:
    serious: list[str] = []
    warnings: list[str] = []
    relative = path.relative_to(PROJECT_ROOT)

    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(relative))
    except (OSError, SyntaxError, UnicodeError) as error:
        return [f"{relative}: could not parse ({error})"], warnings

    is_ui = _is_ui_file(path)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = _module_name(node)
            if not is_ui and (
                module == "streamlit"
                or module.startswith("streamlit.")
                or "streamlit" in module.split(",")
            ):
                serious.append(f"{relative}:{node.lineno}: Streamlit import in core module")
            if not is_ui and (
                module == "src.ui_streamlit"
                or module.startswith("src.ui_streamlit.")
            ):
                serious.append(f"{relative}:{node.lineno}: core imports Streamlit UI layer")
            if is_ui and module == "sqlite3":
                warnings.append(f"{relative}:{node.lineno}: UI imports sqlite3 directly")

        if isinstance(node, ast.Attribute):
            if (
                not is_ui
                and isinstance(node.value, ast.Name)
                and node.value.id == "st"
                and node.attr == "session_state"
            ):
                serious.append(f"{relative}:{node.lineno}: session_state used in core module")

        if is_ui and isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _looks_like_sql(node.value):
                warnings.append(f"{relative}:{node.lineno}: possible direct SQL in UI")

        if (
            is_ui
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sqlite3"
            and node.func.attr == "connect"
        ):
            warnings.append(f"{relative}:{node.lineno}: UI opens SQLite directly")

    return serious, warnings


def main() -> int:
    python_files = [PROJECT_ROOT / "app.py"]
    python_files.extend(sorted(SRC_DIR.rglob("*.py")))

    serious: list[str] = []
    warnings: list[str] = []
    for path in python_files:
        file_serious, file_warnings = audit_file(path)
        serious.extend(file_serious)
        warnings.extend(file_warnings)

    print("Vocabulary App architecture audit")
    print(f"Scanned {len(python_files)} Python files.")

    if serious:
        print("\nSerious boundary violations:")
        for issue in serious:
            print(f"- {issue}")
    else:
        print("\nSerious boundary violations: none")

    if warnings:
        print("\nWarnings for manual review:")
        for issue in sorted(set(warnings)):
            print(f"- {issue}")
    else:
        print("Warnings for manual review: none")

    return 1 if serious else 0


if __name__ == "__main__":
    raise SystemExit(main())
