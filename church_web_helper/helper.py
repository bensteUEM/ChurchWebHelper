"""File which includes helpful methods for data transformation in the context of ChurchWebHelper.

It is used to outsource parts which don't need to be part of app.py
"""

from collections import OrderedDict
from churchtools_api.churchtools_api import ChurchToolsApi as CTAPI
from dateutil.relativedelta import relativedelta

from datetime import datetime
import docx
from docx.shared import Pt
import docx.table
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

    for index, df_row in data.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = df_row["shortDay"]
        for paragraph in row_cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True
        for column_no, location in enumerate(locations):
            generate_event_paragraph(
                target_cell=row_cells[1 + column_no], relevant_entry=df_row[location]
            )

    change_font_of_table(table=table)

    FOOTER_TEXT = "Sonntags um 10.00 Uhr findet regelmäßig Kinderkirche in Baiersbronn statt. Bei Interesse melden Sie sich bitte direkt bei den Mitarbeitenden.: Juliane Haas, Tel: 604467 oder Bärbel Vögele, Tel.:121136"
    document.add_paragraph(FOOTER_TEXT)

    return document


def deduplicate_df_index_with_lists(df_input: pd.DataFrame) -> pd.DataFrame:
    """Flattens a df with multiple same index entries to list entries

    Args:
        df_input: the original dataframe which contains multiple entries for "shortDay" index per column

    Returns:
        flattened df which has unique shortDay and combined lists in cells
    """

    shortDays = list(OrderedDict.fromkeys(df_input["shortDay"]).keys())
    df_output = pd.DataFrame(columns=df_input.columns)
    for shortDay in shortDays:
        df_shortDay = df_input[df_input["shortDay"] == shortDay]
        new_index = len(df_output)
        df_output.loc[new_index] = [pd.NA] * df_output.shape[1]
        df_output.iloc[new_index]["shortDay"] = shortDay

        locations = OrderedDict.fromkeys(i[0] for i in df_shortDay.columns[1:])
        for location in locations:
            for col in df_shortDay[location]:
                value_list = []
                df_non_empty = df_shortDay[location][
                    ~(
                        df_shortDay[location].apply(
                            lambda row: (row == "").all(), axis=1
                        )
                    )
                ]
                for value in df_non_empty[col]:
                    if isinstance(value, list):
                        value_list.extend(value)
                    else:
                        value_list.append(value)
                df_output.loc[new_index, (location, col)] = value_list

    df_output = df_output.fillna("")

    return df_output


def generate_event_paragraph(
    target_cell: docx.table._Cell, relevant_entry: pd.Series
) -> None:
    """function which generates the content of one table cell.

    Used with get_plan_months_docx
    Iterates through all items in relevant row and using the columns to generate the text.

    Args:
        target_cell: the table cell which should get the content
        relevant_row: the pd series with list of items in each column

    Returns:
        None because working inplace
    """
    for entry_index in range(1 - 1, len(relevant_entry["shortTime"])):
        current_paragraph = (
            target_cell.paragraphs[0]
            if entry_index == 0
            else target_cell.add_paragraph("")
        )
        if relevant_entry["shortTime"][entry_index]:
            # TODO #16 something is off here ... same time for all on web export
            current_paragraph.add_run(relevant_entry["shortTime"][entry_index])
        if relevant_entry["shortName"][entry_index]:
            # should be single relevant_row only but getting list
            current_paragraph.add_run(" " + relevant_entry["shortName"][entry_index])

        # Apply bold formatting nad set font size and font family
        for run in current_paragraph.runs:
            run.bold = True

        if relevant_entry["specialService"][entry_index]:
            current_paragraph.runs[-1].add_break()
            current_paragraph.add_run(
                " " + relevant_entry["specialService"][entry_index]
            )
        if relevant_entry["predigt"][entry_index]:
            current_paragraph.runs[-1].add_break()
            current_paragraph.add_run(f"({relevant_entry["predigt"][entry_index]})")


def change_font_of_table(table: docx.table) -> None:
    """Inplace overwrite of font styles commonly used for all columns.

    Args:
        table: the table to iterate
    """
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "ArialNarrow"
                    run.font.size = Pt(15)
