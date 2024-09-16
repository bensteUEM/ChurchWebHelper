from datetime import datetime
import os
import pytest

from church_web_helper.helper import (
    extract_relevant_calendar_appointment_shortname,
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
