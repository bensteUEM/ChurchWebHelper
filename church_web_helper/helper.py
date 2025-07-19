"""File which includes helpful methods for data transformation.

It is used to outsource parts which don't need to be part of app.py
"""

import logging
from collections import OrderedDict
from datetime import datetime

import pandas as pd
from churchtools_api.churchtools_api import ChurchToolsApi
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def get_special_day_name(
    ct_api: ChurchToolsApi, special_name_calendar_ids: list[int], date: datetime
) -> str:
    """Retrieve the name of the first calendarf entry one a specific day.

    This can be used to retrieve "holiday" names if they are specfied in the calendar

    Args:
        ct_api: initialized churchtools api connection used as datasource
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
    if special_names and len(special_names) > 0:
        return special_names[0]["caption"]

    return ""


def extract_relevant_calendar_appointment_shortname(longname: str) -> str:
    """Tries to extract a shortname for "special ocasion events" based on a mapping.

    Excecution order is relevant!

    Args:
        longname (str): the original title of the event

    Returns:
        str: the shortened version which only includes special parts.
            Does return empty str if nothing detected
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


def deduplicate_df_index_with_lists(df_input: pd.DataFrame) -> pd.DataFrame:
    """Flattens a df with multiple same index entries to list entries.

    Args:
        df_input: the original dataframe which contains multiple entries
            for "shortDay" index per column

    Returns:
        flattened df which has unique shortDay and combined lists in cells
    """
    shortDays = list(OrderedDict.fromkeys(df_input["shortDay"]).keys())
    df_output = pd.DataFrame(columns=df_input.columns)
    for shortDay in shortDays:
        df_shortDay = df_input[df_input["shortDay"] == shortDay]
        new_index = len(df_output)
        df_output.loc[new_index] = [pd.NA] * df_output.shape[1]
        df_output.loc[new_index, "shortDay"] = df_shortDay["shortDay"].iloc[0]
        df_output.loc[new_index, "specialDayName"] = df_shortDay["specialDayName"].iloc[
            0
        ]

        locations = OrderedDict.fromkeys(i[0] for i in df_shortDay.columns[2:])
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
    logger.debug("finished deduplicate_df_index_with_lists")

    return df_output


def get_primary_resource(
    appointment_id: int,
    relevant_date: datetime,
    ct_api: ChurchToolsApi,
    considered_resource_ids: list[int],
) -> str:
    """Helper which is used to get the primary resource allocation of an event.

    Args:
        appointment_id: id of calendar entry
        relevant_date: the date of the appointment is required
            because appointment_id is not unique on repetitions
        ct_api: initialized churchtools api connection used as datasource
        considered_resource_ids: resource ids to consider
            ignores negative numbers as special case on purpse

    Returns:
        shortened resource representation
    """
    considered_resource_ids = [
        resource_id for resource_id in considered_resource_ids if resource_id > 0
    ]

    bookings = ct_api.get_bookings(
        resource_ids=considered_resource_ids,
        from_=relevant_date,
        to_=relevant_date,
        appointment_id=appointment_id,
    )
    return {booking["base"]["resource"]["name"] for booking in bookings}
