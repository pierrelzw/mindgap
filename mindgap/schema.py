"""v2 analysis schema: passed to `claude --json-schema` and re-checked locally."""
from __future__ import annotations

ANALYSIS_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blindspot", "evidence", "root_cause", "book", "checklist", "one_liner", "confidence"],
    "properties": {
        "blindspot": {
            "type": "object",
            "additionalProperties": False,
            "required": ["label_en", "label_zh", "definition"],
            "properties": {
                "label_en": {"type": "string"},
                "label_zh": {"type": "string"},
                "definition": {"type": "string"},
            },
        },
        "evidence": {
            "type": "array", "minItems": 2, "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["time", "sessionId", "quote", "why_it_matters"],
                "properties": {
                    "time": {"type": "string"},
                    "sessionId": {"type": "string"},
                    "quote": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                },
            },
        },
        "root_cause": {"type": "string"},
        "book": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "author", "year", "principle", "why"],
            "properties": {
                "title": {"type": "string"},
                "author": {"type": "string"},
                "year": {"type": "integer"},
                "principle": {"type": "string"},
                "why": {"type": "string"},
            },
        },
        "checklist": {"type": "array", "minItems": 3, "maxItems": 5, "items": {"type": "string"}},
        "one_liner": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}


def _check(obj, schema, path, errs):
    t = schema.get("type")
    if t == "object":
        if not isinstance(obj, dict):
            errs.append(f"{path}: 应为 object")
            return
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}.{k}: 缺失")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in props:
                    errs.append(f"{path}.{k}: 多余字段")
        for k, sub in props.items():
            if k in obj:
                _check(obj[k], sub, f"{path}.{k}", errs)
    elif t == "array":
        if not isinstance(obj, list):
            errs.append(f"{path}: 应为 array")
            return
        lo, hi = schema.get("minItems"), schema.get("maxItems")
        if lo is not None and len(obj) < lo:
            errs.append(f"{path}: 至少 {lo} 项，实际 {len(obj)}")
        if hi is not None and len(obj) > hi:
            errs.append(f"{path}: 至多 {hi} 项，实际 {len(obj)}")
        for i, x in enumerate(obj):
            _check(x, schema["items"], f"{path}[{i}]", errs)
    elif t == "string":
        if not isinstance(obj, str):
            errs.append(f"{path}: 应为 string")
        elif not obj.strip():
            errs.append(f"{path}: 不能为空")
        elif "enum" in schema and obj not in schema["enum"]:
            errs.append(f"{path}: 必须是 {schema['enum']}")
    elif t == "integer":
        if not isinstance(obj, int) or isinstance(obj, bool):
            errs.append(f"{path}: 应为 integer")


def validate(obj) -> list[str]:
    """Return a list of human-readable problems; empty means valid."""
    errs: list[str] = []
    _check(obj, ANALYSIS_SCHEMA, "$", errs)
    return errs
