"""Reading complaint files: CSV/Excel, headers, limits, formula escaping."""

import io

import pytest
from openpyxl import Workbook

from bulk_import.reader import ImportFileError, escape_cell, read_rows, template_csv

HEADER = "Customer_Email,customer_name,TITLE,description,extra\n"
ROW = "sara@example.test,Sara,Late order,My order is two weeks late and nobody replies.,x\n"


def test_csv_with_bom_and_mixed_case_headers() -> None:
    rows, unknown = read_rows("c.csv", ("﻿" + HEADER + ROW).encode())
    assert rows == [
        {
            "customer_email": "sara@example.test",
            "customer_name": "Sara",
            "title": "Late order",
            "description": "My order is two weeks late and nobody replies.",
        }
    ]
    assert unknown == ["extra"]


def test_xlsx() -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["customer_email", "title", "description", "received_at"])
    sheet.append(["a@example.test", "Broken", "The charger sparked when plugged in.", "2026-09-20"])
    buffer = io.BytesIO()
    book.save(buffer)
    rows, _ = read_rows("C.XLSX", buffer.getvalue())
    assert rows[0]["received_at"].startswith("2026-09-20")


def test_blank_rows_are_skipped() -> None:
    rows, _ = read_rows("c.csv", (HEADER + ",,,,\n" + ROW + "\n").encode())
    assert len(rows) == 1


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("c.txt", b"x", "CSV or .xlsx"),
        ("c.csv", b"title\nx\n", "customer_email"),
        ("c.csv", (HEADER + ROW * 1001).encode(), "1,000"),
        ("c.csv", b"", "empty"),
        ("c.csv", b"\xff\xfe\x00bad", "UTF-8"),
        ("c.xlsx", b"not a zip", "could not be read"),
        ("c.csv", b"0" * (5 * 1024 * 1024 + 1), "5 MB"),
    ],
    ids=["type", "missing-column", "too-many", "empty", "encoding", "bad-xlsx", "too-big"],
)
def test_bad_files(name: str, data: bytes, message: str) -> None:
    with pytest.raises(ImportFileError, match=message):
        read_rows(name, data)


def test_formula_cells_are_neutralised() -> None:
    assert escape_cell('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert escape_cell("@SUM(A1)") == "'@SUM(A1)" and escape_cell("-1") == "'-1"
    assert escape_cell("+44 20") == "'+44 20" and escape_cell("fine") == "fine"


def test_template_has_every_column() -> None:
    header = template_csv().decode().splitlines()[0]
    assert header.startswith("customer_email,customer_name,title,description")
