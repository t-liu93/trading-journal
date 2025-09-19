import ast
import json
import sys
from pathlib import Path

# Ensure the "backend" package directory is on sys.path so `import trading_journal` works
# Find repo root by walking upwards until we find a "backend" directory.
p = Path(__file__).resolve()
repo_root = None
while True:
    if (p / "backend").exists():
        repo_root = p
        break
    if p.parent == p:
        break
    p = p.parent
# fallback: two levels up (covers common .github/script layout)
if repo_root is None:
    repo_root = Path(__file__).resolve().parents[2]

backend_dir = repo_root / "backend"
if backend_dir.exists():
    sys.path.insert(0, str(backend_dir))


def load_struct(path: Path):
    src = path.read_text(encoding="utf-8")
    mod = ast.parse(src)
    out = {}
    for node in mod.body:
        if not isinstance(node, ast.ClassDef):
            continue
        # detect SQLModel table classes:
        is_table = any(
            (
                kw.arg == "table"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            )
            for kw in getattr(node, "keywords", [])
        ) or any(
            getattr(b, "id", None) == "SQLModel"
            or getattr(getattr(b, "attr", None), "id", None) == "SQLModel"
            for b in getattr(node, "bases", [])
        )
        if not is_table:
            continue
        fields = []
        for item in node.body:
            # annotated assignment: name: type = value
            if isinstance(item, ast.AnnAssign) and getattr(item.target, "id", None):
                name = item.target.id
                ann = (
                    ast.unparse(item.annotation)
                    if item.annotation is not None
                    else None
                )
                val = ast.unparse(item.value) if item.value is not None else None
                fields.append((name, ann, val))
            # simple assign: name = value (rare for Field, but include)
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    if getattr(t, "id", None):
                        name = t.id
                        ann = None
                        val = (
                            ast.unparse(item.value) if item.value is not None else None
                        )
                        fields.append((name, ann, val))
        # sort fields by name for deterministic comparison
        fields.sort(key=lambda x: x[0])
        out[node.name] = fields
    return out


def main():
    if len(sys.argv) == 1:
        print(
            "usage: compare_models.py <live_model_path> [snapshot_model_path]",
            file=sys.stderr,
        )
        sys.exit(2)

    live = Path(sys.argv[1])
    snap = None
    if len(sys.argv) >= 3:
        snap = Path(sys.argv[2])
    else:
        # auto-detect snapshot via db_migration.LATEST_VERSION
        try:
            import importlib

            dbm = importlib.import_module("trading_journal.db_migration")
            latest = getattr(dbm, "LATEST_VERSION")
            snap = Path(live.parent) / f"models_v{latest}.py"
        except Exception as e:
            print("failed to determine snapshot path:", e, file=sys.stderr)
            sys.exit(2)

    if not live.exists() or not snap.exists():
        print(
            f"file missing: live={live.exists()} snap={snap.exists()}", file=sys.stderr
        )
        sys.exit(2)

    a = load_struct(live)
    b = load_struct(snap)
    if a != b:
        print("models mismatch\n")
        diff = {
            "live_only_classes": sorted(set(a) - set(b)),
            "snapshot_only_classes": sorted(set(b) - set(a)),
            "mismatched_classes": {},
        }
        for cls in set(a) & set(b):
            if a[cls] != b[cls]:
                diff["mismatched_classes"][cls] = {"live": a[cls], "snapshot": b[cls]}
        print(json.dumps(diff, indent=2, ensure_ascii=False))
        sys.exit(1)
    print("models match snapshot")
    sys.exit(0)


if __name__ == "__main__":
    main()
