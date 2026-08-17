"""Parser tests using a redacted column-text fixture (no PII)."""
from __future__ import annotations

import unittest
from pathlib import Path

from parse import dedupe_courses, parse_column_text, parse_course_line, parse_transcript_pdf

FIXTURE = """
Fall 2024 Undergraduate LSA Grade Hours MSH CTP MHP
Transfer Test Credit
Advanced Placement
BIOLOGY 195 Introductory Biology T 0.00 0.00 5.00 0.00
CHEM 125 Gen Chem Lab I T 0.00 0.00 1.00 0.00
MATH 120 Exam Calc Credit I T 0.00 0.00 4.00 0.00
STATS 180 AP Statistics T 0.00 0.00 3.00 0.00
Fall 2024 Undergraduate LSA Grade Hours MSH CTP MHP
Transfer Course Credit Washtenaw Community College
MATH 214 App Linear Algebra T 0.00 0.00 4.00 0.00
Fall 2024 Undergraduate LSA Grade Hours MSH CTP MHP
EECS 183 Elem Prog Concepts A 4.00 4.00 4.00 16.00
ENGLISH 125 Writing&Academic Inq A 4.00 4.00 4.00 16.00
PHYSICS 141 Elem Lab I A+ 1.00 1.00 1.00 4.00
PUBHLTH 200 Health & Society B 4.00 4.00 4.00 12.00
Term Total GPA: 3.764 17.00 17.00 17.00 64.00
Winter 2025 Undergraduate LSA Grade Hours MSH CTP MHP
BIOLOGY 173 Intro Biol Lab A 2.00 2.00 2.00 8.00
CHEM 210 Struct & React I A- 3.00 3.00 3.00 11.10
Fall 2025 Undergraduate LSA Grade Hours MSH CTP MHP
ALA 280 Undergrad Research Y 2.00 0.00 0.00 0.00
EECS 280 Prog&Data Struct A- 4.00 4.00 4.00 14.80
Winter 2026 Undergraduate LSA Grade Hours MSH CTP MHP
ALA 280 Undergrad Research 3.00 0.00 0.00 0.00
EECS 281 Data Struct&Algor 4.00 0.00 0.00 0.00
Spring 2026 Undergraduate LSA Grade Hours MSH CTP MHP
Elections as of: 04/23/2026
EECS 370 Intro Computer Org 4.00 0.00 0.00 0.00
STATS 425 Intro Probability 3.00 0.00 0.00 0.00
Elected Term Hours 7.00
"""


class ParseTests(unittest.TestCase):
    def test_transfer_uses_ctp_credits(self):
        row = parse_course_line(
            "BIOLOGY 195 Introductory Biology T 0.00 0.00 5.00 0.00"
        )
        self.assertEqual(row["course_code"], "BIOLOGY 195")
        self.assertEqual(row["grade"], "T")
        self.assertEqual(row["credits"], 5.0)

    def test_letter_grade(self):
        row = parse_course_line("CHEM 210 Struct & React I A- 3.00 3.00 3.00 11.10")
        self.assertEqual(row["course_code"], "CHEM 210")
        self.assertEqual(row["grade"], "A-")
        self.assertEqual(row["credits"], 3.0)

    def test_in_progress_no_grade(self):
        row = parse_course_line("EECS 281 Data Struct&Algor 4.00 0.00 0.00 0.00")
        self.assertIsNone(row["grade"])
        self.assertEqual(row["hours"], 4.0)

    def test_column_statuses(self):
        courses = parse_column_text(FIXTURE)
        by = {c["course_code"]: c for c in courses}
        self.assertEqual(by["BIOLOGY 195"]["status"], "completed")
        self.assertEqual(by["EECS 183"]["status"], "completed")
        self.assertEqual(by["CHEM 210"]["term_completed"], "Winter 2025")
        self.assertEqual(by["EECS 281"]["status"], "in_progress")
        self.assertEqual(by["EECS 370"]["status"], "enrolled")
        self.assertEqual(by["STATS 425"]["status"], "enrolled")

    def test_dedupe_prefers_completed(self):
        rows = parse_column_text(FIXTURE)
        # ALA 280 appears as Y then in-progress — keep in_progress over enrolled, but Y is in_progress
        deduped = dedupe_courses(rows)
        ala = [c for c in deduped if c["course_code"] == "ALA 280"]
        self.assertEqual(len(ala), 1)
        self.assertEqual(ala[0]["status"], "in_progress")

    def test_skips_headers(self):
        codes = {c["course_code"] for c in parse_column_text(FIXTURE)}
        self.assertNotIn("TERM TOTAL", codes)


class PdfSmokeTest(unittest.TestCase):
    def test_real_pdf_if_present(self):
        pdf = Path(
            "/Users/adharvprerepa/.cursor/projects/Users-adharvprerepa-Course-Guide/"
            "attachments/e7cf2f8d-b84c-4dbf-9b6c-234431571632/SSR_TSRPT_SC__2_.pdf"
        )
        if not pdf.exists():
            self.skipTest("sample PDF not in workspace")
        result = parse_transcript_pdf(pdf.read_bytes())
        codes = {c["course_code"] for c in result["courses"]}
        self.assertIn("EECS 280", codes)
        self.assertIn("BIOLOGY 195", codes)
        self.assertIn("MATH 214", codes)
        self.assertGreaterEqual(result["counts"]["completed"], 20)
        eecs280 = next(c for c in result["courses"] if c["course_code"] == "EECS 280")
        self.assertEqual(eecs280["status"], "completed")
        eecs370 = next(c for c in result["courses"] if c["course_code"] == "EECS 370")
        self.assertEqual(eecs370["status"], "enrolled")


if __name__ == "__main__":
    unittest.main()
