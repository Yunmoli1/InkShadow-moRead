"""扫描 f-string 表达式中的反斜杠（Python 3.11 语法错误，3.12+ 才放行）。"""
import ast
import sys
from pathlib import Path

BACKSLASH = chr(92)


def scan(root: str):
    hits = []
    for p in sorted(Path(root).rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FormattedValue):
                for seg_node in (node.value, node.format_spec):
                    seg = ast.get_source_segment(src, seg_node) if seg_node else None
                    if seg and BACKSLASH in seg:
                        hits.append((str(p), node.lineno, seg[:70]))
    return hits


hits = []
for root in sys.argv[1:] or ["app", "tests"]:
    hits += scan(root)
print("f-string backslash hits:", len(hits))
for path, line, seg in hits:
    print(f"{path}:{line}: {seg}")
