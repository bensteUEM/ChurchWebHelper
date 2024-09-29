from datetime import datetime
import os
import pandas as pd
import pytest
import docx

from church_web_helper.helper import (
    extract_relevant_calendar_appointment_shortname,
    get_plan_months_docx,
    get_primary_resource,
    get_special_day_name,
)
from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI


class Test_Helper:
    def setup_method(self) -> None:
        self.ct_api = CTAPI(
            domain=os.getenv("CT_DOMAIN"), ct_token=os.getenv("CT_TOKEN")
        )

    # Parametrized pytest function
    @pytest.mark.parametrize(
        "input, expected_output",
        [
            ("Abendmahl", "mit Abendmahl"),
            ("Familien", "für Familien"),
            ("Grünen", "im Grünen"),
            ("im Sankenbach", "im Grünen"),
            ("auf der Schelkewiese", "im Grünen"),
            ("auf der Gartenschau", "im Grünen"),
            ("Konfirmation", "Konfirmation"),
            ("Goldene Konfirmation", "Konfirmation"),
            ("Ökumenisch", "Ökumenisch"),
            ("Ökum. Gottesdienst", "Ökumenisch"),
            ("Wohnzimmer-Worship", "Wohnzimmer-Worship"),
            ("CVJM-Sonntag", "CVJM"),
            ("Impulsgodi", "Impuls"),
        ],
    )
    def test_extract_relevant_calendar_appointment_shortname(
        self, input: str, expected_output: str
    ):
        assert (
            extract_relevant_calendar_appointment_shortname(longname=input)
            == expected_output
        )

    @pytest.mark.parametrize(
        "date, expected_output",
        [
            (datetime(year=2024, month=12, day=23, hour=23), ""),
            (datetime(year=2024, month=12, day=24), "Christvesper"),
            (datetime(year=2024, month=12, day=25), "Christfest I"),
            (datetime(year=2024, month=12, day=26), "Christfest II"),
            (datetime(year=2024, month=12, day=26, hour=23), "Christfest II"),
        ],
    )
    def test_get_special_day_name(self, date: datetime, expected_output: str):
        special_name_calendar_ids = [52, 72]

        assert (
            get_special_day_name(
                ct_api=self.ct_api,
                special_name_calendar_ids=special_name_calendar_ids,
                date=date,
            )
            == expected_output
        )

    def test_get_plan_months_docx(self):
        df_sample = pd.DataFrame(
            {
                "shortDay": ["3.2", "23.1", "23.1", "3.2"],
                "startDate": [
                    datetime(year=2024, month=2, day=3),
                    datetime(year=2024, month=1, day=23),
                    datetime(year=2024, month=1, day=23),
                    datetime(year=2024, month=2, day=3),
                ],
                "location": ["A1", "A2", "A2", "A3"],
                "shortTime": ["08:00", "10:00", "12:00", "9:00"],
                "predigt": ["P1", "P2", "P1", "P2"],
                "shortName": ["mit Abendmahl", None, None, None],
                "specialService": [None, "mit Kirchenchor", None, None],
            }
        )
        df_data = (
            df_sample.pivot_table(
                values=["shortTime", "shortName", "predigt", "specialService"],
                index=["startDate", "shortDay"],
                columns=["location"],
                aggfunc=list,
                fill_value="",
            )
            .reorder_levels([1, 0], axis=1)
            .sort_index(axis=1)
            .reset_index()
            .drop(columns="startDate")
        )

        FILENAME = "tests/samples/test_get_plan_months.docx"
        expected_sample = docx.Document(FILENAME)

        result = get_plan_months_docx(
            df_data, from_date=datetime(year=2024, month=1, day=1)
        )

        assert compare_docx_files(result, expected_sample)

    def test_get_primary_resource(self):
        SAMPLE_EVENT_ID = 330754
        SAMPLE_DATE = datetime(year=2024, month=9, day=29)
        EXPECTED_RESULT = {'Michaelskirche (MIKI)'}
        RESOURCE_IDS = [8,16,17,20,21]

        result = get_primary_resource(appointment_id=SAMPLE_EVENT_ID,
                                    relevant_date=SAMPLE_DATE,
                                    api=self.ct_api,
                                    considered_resource_ids=RESOURCE_IDS,
                                    )

        assert EXPECTED_RESULT == result

def test_compare_docx_files():
    FILENAME = "tests/samples/test_get_plan_months.docx"
    FILENAME2 = "tests/samples/test_get_plan_months_other.docx"

    doc1 = docx.Document(FILENAME)
    doc2 = docx.Document(FILENAME)
    assert compare_docx_files(doc1, doc2)[0]

    doc3 = docx.Document(FILENAME2)
    assert not compare_docx_files(doc1, doc3)[0]


def compare_docx_files(
    document1: docx.Document, document2: docx.Document
) -> (bool, str):
    """Compare both text and table content of two docx files.

    Args:
        document1: _description_
        document2: _description_

    Returns:
        bool - if is equal
        text - description of difference
    """

    # Compare text
    text1 = get_docx_text(document1)
    text2 = get_docx_text(document2)

    if text1 != text2:
        return False, "Text is different"

    # Compare tables
    tables1 = get_docx_tables(document1)
    tables2 = get_docx_tables(document2)

    if not compare_tables(tables1, tables2):
        return False, "Tables are different"

    return True, "Files are identical"


def get_docx_text(document):
    """Extract text content from the docx file."""
    full_text = []
    for para in document.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)


def get_docx_tables(document):
    """Extract tables content from the docx file."""
    tables = []

    for table in document.tables:
        table_content = []
        for row in table.rows:
            row_content = []
            for cell in row.cells:
                row_content.append(cell.text.strip())
            table_content.append(row_content)
        tables.append(table_content)

    return tables


def compare_tables(tables1, tables2):
    """Compare two sets of tables."""
    if len(tables1) != len(tables2):
        return False

    for table1, table2 in zip(tables1, tables2):
        if len(table1) != len(table2):
            return False

        for row1, row2 in zip(table1, table2):
            if row1 != row2:
                return False

    return True