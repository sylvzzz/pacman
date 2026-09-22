import os
from typing import Iterator, List

# Whole repo fits well under this budget, so the import graph is unnecessary:
# every .py file goes into the context. Add back per-import resolution only if
# the project grows past MAX_BYTES.
MAX_BYTES = 300_000
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__",
    "build", "dist", ".mypy_cache", ".pytest_cache",
}


def py_files() -> Iterator[str]:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.relpath(os.path.join(root, name), ".")


def changed_files(base_ref: str) -> List[str]:
    # PR events pass a branch name; push events pass a commit SHA.
    ref = f"origin/{base_ref}"
    if os.system(f"git rev-parse --verify --quiet {ref} > /dev/null"):
        ref = base_ref
    out = os.popen(f"git diff {ref}...HEAD --name-only -- '*.py'").read()
    return [f for f in out.splitlines() if f.strip()]


def write_context(base_ref: str) -> bool:
    changed = changed_files(base_ref)
    if not changed:
        return False

    body = (
        "=== CHANGED FILES (repo paths) ===\n"
        + "\n".join(changed)
        + "\n\n=== REPO CONTEXT (current file contents) ===\n"
    )

    for f in py_files():
        try:
            with open(f, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        if len(body) + len(content) > MAX_BYTES:
            body += (f"\n\n[context truncated at {MAX_BYTES} bytes; "
                     f"first omitted: {f}]")
            break
        body += f"\n\n### FILE: {f}\n{content}"

    with open("context.txt", "w", encoding="utf-8") as fh:
        fh.write(body)
    return True


def main() -> None:
    base_ref = os.environ["BASE_REF"]
    if write_context(base_ref):
        print("context.txt written")
    else:
        print("no .py changes; context.txt skipped")


if __name__ == "__main__":
    main()
