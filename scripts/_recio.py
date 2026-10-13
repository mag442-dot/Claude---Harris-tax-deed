"""Safe record writes for scripts that run concurrently: re-read the file right before
writing and replace only the sections this script owns (plus a union of human_blockers)."""
import json
from pathlib import Path


def save_sections(path, rec, sections):
    path = Path(path)
    fresh = json.loads(path.read_text())
    for s in sections:
        if s in rec:
            fresh[s] = rec[s]
    blockers = fresh.get("human_blockers", [])
    for b in rec.get("human_blockers", []):
        if b not in blockers:
            blockers.append(b)
    if blockers:
        fresh["human_blockers"] = blockers
    path.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n")
