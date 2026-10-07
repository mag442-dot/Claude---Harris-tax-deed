#!/usr/bin/env python3
"""Validate property record JSONs against the schema plus evidence rules.

Usage: python3 scripts/validate_record.py <records-dir-or-file>

Checks:
  - JSON Schema (requires `pip install jsonschema`)
  - a finding with status "verified" must have a non-empty `source`
  - a finding with status "blocked" requires at least one human_blockers entry
  - review.decision == "COMPRA FUERTE" requires a numeric bid_ceiling and no
    blocked findings in tax/title/legal
Exit code 1 if any record has errors.
"""
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("Missing dependency: pip install jsonschema")

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "property_record.schema.json"
SECTIONS = ("intake", "tax", "title", "legal", "physical", "valuation")


def check(rec, validator):
    errors = [f"schema: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
              for e in validator.iter_errors(rec)]
    any_blocked = False
    blocked_core = False
    for sec in SECTIONS:
        for key, f in (rec.get(sec) or {}).items():
            if not isinstance(f, dict):
                continue
            st = f.get("status")
            if st == "verified" and not f.get("source"):
                errors.append(f"evidence: {sec}.{key} is 'verified' without a source")
            if st == "blocked":
                any_blocked = True
                if sec in ("tax", "title", "legal"):
                    blocked_core = True
    if any_blocked and not rec.get("human_blockers"):
        errors.append("evidence: blocked finding(s) but no human_blockers entry")
    review = rec.get("review") or {}
    if review.get("decision") == "COMPRA FUERTE":
        if not isinstance(review.get("bid_ceiling"), (int, float)):
            errors.append("review: COMPRA FUERTE requires a numeric bid_ceiling")
        if blocked_core:
            errors.append("review: COMPRA FUERTE with blocked items in tax/title/legal")
    return errors


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    target = Path(argv[1])
    files = [target] if target.is_file() else sorted(target.glob("*.json"))
    if not files:
        sys.exit(f"No records in {target}")
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text()))
    bad = 0
    for f in files:
        try:
            errs = check(json.loads(f.read_text()), validator)
        except json.JSONDecodeError as e:
            errs = [f"invalid JSON: {e}"]
        if errs:
            bad += 1
            print(f"FAIL {f}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"OK   {f}")
    print(f"{len(files) - bad}/{len(files)} records valid")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv)
