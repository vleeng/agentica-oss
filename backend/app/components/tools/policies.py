from __future__ import annotations

import ipaddress
import json
import re


def extract_search_payload(raw_query: str) -> tuple[str, int]:
    text = str(raw_query or "").strip()
    default_results = 5
    if not text:
        return "", default_results

    try:
        payload = json.loads(text)
    except Exception:
        return text, default_results

    if isinstance(payload, dict):
        query = str(payload.get("query") or payload.get("input") or text).strip()
        max_results = payload.get("max_results", default_results)
        try:
            max_results = max(1, min(int(max_results), 10))
        except Exception:
            max_results = default_results
        return query or text, max_results

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            query = str(first.get("query") or first.get("input") or text).strip()
            max_results = first.get("max_results", default_results)
            try:
                max_results = max(1, min(int(max_results), 10))
            except Exception:
                max_results = default_results
            return query or text, max_results

    return text, default_results


def extract_table_names(query: str) -> set[str]:
    matches = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_\.]*)", query, flags=re.IGNORECASE)
    normalized: set[str] = set()
    for match in matches:
        table = match.split(".")[-1].strip().strip('"').strip("'")
        if table:
            normalized.add(table.lower())
    return normalized


def query_uses_allowed_tables(query: str, allowed_tables: list[str]) -> bool:
    if not allowed_tables:
        return True
    referenced = extract_table_names(query)
    allowed = {table.lower() for table in allowed_tables}
    return referenced.issubset(allowed)


def is_private_host(hostname: str) -> bool:
    if not hostname:
        return True
    lowered = hostname.lower()
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local
