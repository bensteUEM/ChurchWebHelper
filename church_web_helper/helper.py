"""File which includes helpful methods for data transformation in the context of ChurchWebHelper.

It is used to outsource parts which don't need to be part of app.py
"""

from collections import OrderedDict
from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from dateutil.relativedelta import relativedelta

from datetime import datetime
import docx
from docx.shared import Pt
import pandas as pd


def get_special_day_name(
    ct_api: CTAPI, special_name_calendar_ids: list[int], date: datetime
) -> str:
    """Retrieve the name of the first calendarf entry one a specific day.

    This can be used to retrieve "holiday" names if they are specfied in the calendar

    Args:
        ct_api: initialized churchtools api connection which should be used as datasource
        special_name_calendar_ids: list of calendar ids used for special names
        date: the day used for lookup

    Returns:
        str: first result of calendar name - usually name of a holiday
    """
    trunc_date = datetime(year=date.year, month=date.month, day=date.day)

    special_names = ct_api.get_calendar_appointments(
        calendar_ids=special_name_calendar_ids,
        from_=trunc_date,
        to_=trunc_date + relativedelta(days=1) - relativedelta(seconds=1),
    )
    if special_names:
        if len(special_names) > 0:
            return special_names[0]["caption"]

    return ""


def extract_relevant_calendar_appointment_shortname(longname: str) -> str:
    """Tries to extract a shortname for "special ocasion events" based on a mapping

    Excecution order is relevant!

    Args:
        longname (str): the original title of the event

    Returns:
        str: the shortened version which only includes special parts. Does return empty str if nothing detected
    """
    longname = longname.upper()
    known_keywords = ["Abendmahl", "Familien", "Grünen", "Konfirmation", "Ökum"]
    for keyword in known_keywords:
        if keyword.upper() in longname:
            result = keyword
            break
    else:
        known_specials = {
            "Sankenbach": "Grünen",
            "Flößerplatz": "Grünen",
            "Gartenschau": "Grünen",
            "Schelkewiese": "Grünen",
            "Wohnzimmer": "Wohnzimmer",
            "CVJM": "CVJM",
            "Impuls": "Impuls",
        }
        for keyword, replacement in known_specials.items():
            if keyword.upper() in longname:
                result = replacement
                break
        else:
            result = ""

    fulltext_replacements = {
        "Abendmahl": "mit Abendmahl",
        "Familien": "für Familien",
        "Grünen": "im Grünen",
        "Wohnzimmer": "Wohnzimmer-Worship",
        "Ökum": "Ökumenisch",
    }
    for old, new in fulltext_replacements.items():
        if result == old:
            result = result.replace(old, new)
            break

    return result


def get_plan_months_docx(data: pd.DataFrame, from_date: datetime) -> docx.Document:
    """Function which converts a Dataframe into a DOCx document used for final print modifications

    Args:
        data: pre-formatted data to be used as base
        from_date: date used for heading

    Returns:
        document reference
    """

    document = docx.Document()
    heading = f"Unsere Gottesdienste im {from_date.strftime("%B %Y")}"
    document.add_heading(heading)

    locations = set([item[0] for item in data.columns[1:]])

    table = document.add_table(rows=1, cols=len(locations) + 1)
    hdr_cells = table.rows[0].cells

    for column_no, content in enumerate(locations):
        hdr_cells[column_no + 1].text = content
        for paragraph in hdr_cells[column_no + 1].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(15)
                run.font.name = "Arial Narrow"

    shortDays = OrderedDict(data["shortDay"]).values()

    for shortDay in shortDays:
        row_cells = table.add_row().cells
        row_cells[0].text = shortDay
        for paragraph in row_cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(15)
                run.font.name = "Arial Narrow"
        for column_no, location in enumerate(locations):
            relevant_row = data[data["shortDay"] == shortDay][location].iloc[0]
            # row_cells[1 + column_no].text = str(row[location])
            for entry_index in range(1 - 1, len(relevant_row["shortTime"])):
                item_head_para = row_cells[1 + column_no].add_paragraph("")
                if relevant_row["shortTime"][
                    entry_index
                ]:  # TODO #16 something is off here ... same time for all on web export
                    item_head_para.add_run(relevant_row["shortTime"][entry_index])
                if relevant_row["shortName"][
                    entry_index
                ]:  # should be single relevant_row only but getting list
                    item_head_para.add_run(" " + relevant_row["shortName"][entry_index])
                # Apply bold formatting nad set font size and font family
                for run in item_head_para.runs:
                    run.bold = True
                    run.font.size = Pt(15)
                    run.font.name = "Arial Narrow"
                # TODO #16 change to runs instead of paragraphs...
                item_body_para = row_cells[1 + column_no].add_paragraph("")
                if relevant_row["specialService"][entry_index]:
                    item_body_para.add_run(
                        " " + relevant_row["specialService"][entry_index]
                    )
                if relevant_row["predigt"][entry_index]:
                    item_body_para.add_run(f" ({relevant_row["predigt"][entry_index]})")

                # Apply font size and font family
                for run in item_body_para.runs:
                    run.font.size = Pt(15)
                    run.font.name = "Arial Narrow"

    FOOTER_TEXT = "Sonntags um 10.00 Uhr findet regelmäßig Kinderkirche in Baiersbronn statt. Bei Interesse melden Sie sich bitte direkt bei den Mitarbeitenden.: Juliane Haas, Tel: 604467 oder Bärbel Vögele, Tel.:121136"
    document.add_paragraph(FOOTER_TEXT)

    return document
