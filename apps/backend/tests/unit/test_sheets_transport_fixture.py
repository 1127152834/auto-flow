"""The recorded Sheets transport has to answer the way Google does.

The push path verifies a write by reading the same cells back with
``valueRenderOption=FORMULA``, because a formula column must come back as the
formula and a literal must come back as the literal it was replaced with. A
stand-in that keeps a stale second view of the same sheet turns every literal
write into a false "远端不一致", which is exactly the kind of stand-in lie the
PM6 acceptance must not carry.
"""

from __future__ import annotations

from tests.fixtures.sheets import FakeSheetsTransport


def test_a_literal_write_replaces_the_formula_view_too() -> None:
    transport = FakeSheetsTransport(
        {"记录": [["编号", "邮箱", "校验"], ["001", "a@example.com", "A@B.COM"]]},
        formulas={
            "记录": [
                ["编号", "邮箱", "校验"],
                ["001", "a@example.com", '=LOWER("A@B.COM")'],
            ]
        },
    )
    transport.send(
        "PUT",
        "https://sheets.googleapis.com/v4/spreadsheets/spreadsheet-1/values/'记录'!$B$2",
        params={"valueInputOption": "RAW"},
        json={"values": [["pushed@example.com"]]},
    )

    grid = transport.send(
        "GET",
        "https://sheets.googleapis.com/v4/spreadsheets/spreadsheet-1/values/'记录'!$B$2",
        params={"valueRenderOption": "FORMULA"},
    )
    assert grid["values"] == [["pushed@example.com"]]
    # A column nobody wrote keeps the formula it always had.
    formula = transport.send(
        "GET",
        "https://sheets.googleapis.com/v4/spreadsheets/spreadsheet-1/values/'记录'!$C$2",
        params={"valueRenderOption": "FORMULA"},
    )
    assert formula["values"] == [['=LOWER("A@B.COM")']]
