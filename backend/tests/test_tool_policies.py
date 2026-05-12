from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.components.tools.policies import (  # noqa: E402
    extract_search_payload,
    extract_table_names,
    is_private_host,
    query_uses_allowed_tables,
)


class ToolPoliciesTest(unittest.TestCase):
    def test_extract_search_payload_plain_text(self):
        query, max_results = extract_search_payload("buscar clima en buenos aires")
        self.assertEqual(query, "buscar clima en buenos aires")
        self.assertEqual(max_results, 5)

    def test_extract_search_payload_dict_json(self):
        query, max_results = extract_search_payload('{"query":"mercado laboral","max_results":9}')
        self.assertEqual(query, "mercado laboral")
        self.assertEqual(max_results, 9)

    def test_extract_search_payload_list_json(self):
        query, max_results = extract_search_payload('[{"query":"people analytics","max_results":3}]')
        self.assertEqual(query, "people analytics")
        self.assertEqual(max_results, 3)

    def test_extract_search_payload_clamps_invalid_range(self):
        query, max_results = extract_search_payload('{"query":"x","max_results":99}')
        self.assertEqual(query, "x")
        self.assertEqual(max_results, 10)

    def test_extract_table_names_from_query(self):
        tables = extract_table_names("SELECT * FROM hr.employees e JOIN payroll ON payroll.emp_id = e.id")
        self.assertEqual(tables, {"employees", "payroll"})

    def test_query_uses_allowed_tables(self):
        self.assertTrue(query_uses_allowed_tables("SELECT * FROM employees", ["employees", "payroll"]))
        self.assertFalse(query_uses_allowed_tables("SELECT * FROM users", ["employees", "payroll"]))

    def test_is_private_host(self):
        self.assertTrue(is_private_host("localhost"))
        self.assertTrue(is_private_host("127.0.0.1"))
        self.assertTrue(is_private_host("10.0.0.4"))
        self.assertFalse(is_private_host("api.openai.com"))


if __name__ == "__main__":
    unittest.main()
