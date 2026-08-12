from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOCS = (
    "README.md",
    "docs/policies/CONTENT_POLICY.md",
    "docs/policies/DATA_SAFETY.md",
    "docs/policies/DATA_STORAGE.md",
    "ARCHITECTURE.md",
    "docs/migration/MIGRATION_READINESS.md",
    "docs/packaging/PACKAGING_FEASIBILITY.md",
    "docs/migration/DESKTOP_MIGRATION_PLAN.md",
)

REQUIRED_IGNORE_RULES = (
    ".venv/",
    "__pycache__/",
    ".env",
    "data/*.db",
    "data/*.sqlite",
    "data/*.sqlite3",
    "!data/.gitkeep",
)


def core_streamlit_imports() -> list[str]:
    issues: list[str] = []
    for path in sorted((PROJECT_ROOT / "src").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "streamlit" for alias in node.names):
                    issues.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "streamlit":
                    issues.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    return issues


def main() -> int:
    warnings: list[str] = []

    for document in REQUIRED_DOCS:
        if not (PROJECT_ROOT / document).is_file():
            warnings.append(f"Missing documentation: {document}")

    gitignore_path = PROJECT_ROOT / ".gitignore"
    gitignore = gitignore_path.read_text(encoding="utf-8-sig") if gitignore_path.is_file() else ""
    for rule in REQUIRED_IGNORE_RULES:
        if rule not in gitignore:
            warnings.append(f"Missing .gitignore rule: {rule}")

    database_path = PROJECT_ROOT / "data" / "vocab.db"
    if database_path.exists():
        warnings.append(
            "Personal database exists locally at data/vocab.db; verify it is excluded "
            "from every release archive and Git commit."
        )

    for location in ("backups", "exports", "user_data"):
        path = PROJECT_ROOT / location
        if path.exists() and any(path.iterdir()):
            warnings.append(f"Local output folder contains files: {location}/")

    for issue in core_streamlit_imports():
        warnings.append(f"Core Streamlit import: {issue}")

    print("Vocabulary App packaging readiness")
    print(f"Project: {PROJECT_ROOT}")
    print(f"Checks completed: {len(REQUIRED_DOCS)} docs, .gitignore, local data, core imports")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("\nNo packaging-readiness warnings found.")

    print("\nThis tool is read-only and does not build or package the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
