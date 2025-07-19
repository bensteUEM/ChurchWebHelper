"""This module implements all helper functions specific to xlsx export."""

import logging
from datetime import datetime

import pandas as pd
import xlsxwriter

logger = logging.getLogger(__name__)


def get_plan_months_xlsx(  # noqa: C901
    data: pd.DataFrame, from_date: datetime, filename: str
) -> xlsxwriter.Workbook:
    """Function which converts a Dataframe into a XLXs used as admin overview printout.

    Args:
        data: pre-formatted data to be used as base
        from_date: date used for heading
        filename: name of the file including extension

    Returns:
        workbook reference
    """
    workbook = xlsxwriter.Workbook(filename)

    heading = f"{from_date.strftime('%B %Y')}"
    worksheet = workbook.add_worksheet(name=heading)

    locations = {item[0] for item in data.columns[2:]}

    row = 0

    # setup 3 header lines
    NUMBER_OF_COLUMNS_PER_LOCATION = 4  # noqa: N806
    format_header = workbook.add_format({"bold": True})
    format_header_b = workbook.add_format({"bold": True, "bottom": 2})
    format_header_bl = workbook.add_format({"bold": True, "bottom": 2, "left": 2})
    format_header_l = workbook.add_format({"bold": True, "left": 2})

    for location_index, location_name in enumerate(locations):
        worksheet.write(
            row,
            location_index * NUMBER_OF_COLUMNS_PER_LOCATION + 1,
            location_name,
            format_header_l,
        )
        for offset, header in enumerate(["Uhr-", "Prediger", "Abm", "Organist"]):
            worksheet.write(
                row + 1,
                1 + location_index * NUMBER_OF_COLUMNS_PER_LOCATION + offset,
                header,
                format_header_l if offset == 0 else format_header,
            )
        for offset, header in enumerate(["zeit", "", "Taufe", "Musik"]):
            worksheet.write(
                row + 2,
                1 + location_index * NUMBER_OF_COLUMNS_PER_LOCATION + offset,
                header,
                format_header_bl if offset == 0 else format_header_b,
            )
    worksheet.set_column(first_col=0, last_col=0, width=20)

    row += 3

    """
    Each location should have a 2*4 entry by eventwhich looks like this

    TIME      | Predigt | ABM   | Organist
    shortName |         | Taufe | Musik

    """

    column_offsets = [0, 1, 2, 3, 0, 1, 2, 3]
    row_offsets = [0, 0, 0, 0, 1, 1, 1, 1]
    column_references = [
        "shortTime",
        "predigt_lastname",
        "abendmahl",
        "organist_lastname",
        "shortName",
        None,
        "taufe",
        "musik",
    ]

    # Iterate all data rows
    location_column_offset = 0
    for _index, df_row in data.iterrows():
        format_content = workbook.add_format({"bold": True, "border": 1})
        format_content_b = workbook.add_format({"bold": True, "border": 1, "bottom": 2})

        worksheet.write(row, 0, df_row["shortDay"].iloc[0], format_content)
        worksheet.write(row + 1, 0, df_row["specialDayName"].iloc[0], format_content_b)

        max_events_per_date = max([len(i) for i in df_row[slice(None), "shortTime"]])
        for row_offset, column_offset, column_value in zip(
            row_offsets, column_offsets, column_references, strict=False
        ):
            for location_index, location in enumerate(locations):
                location_column_offset = location_index * NUMBER_OF_COLUMNS_PER_LOCATION

                for event_per_day_offset in range(max_events_per_date):
                    value = ""
                    if (
                        column_value in df_row[location].index
                        and len(df_row[location, column_value]) > event_per_day_offset
                    ):
                        value = df_row[location, column_value][event_per_day_offset]

                    cell_format = workbook.add_format({"border": 1})
                    if row_offset == 1:
                        cell_format.set_bottom(2)
                    if column_offset == 0:
                        cell_format.set_left(2)

                    worksheet.write(
                        row + row_offset + event_per_day_offset * 2,
                        1 + location_column_offset + column_offset,
                        str(value),
                        cell_format,
                    )

        row += 2 * max_events_per_date
    logger.info("Finished get_plan_months_xlsx")
    return workbook
