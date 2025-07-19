"""All tests in regards to helper.py."""

import json
import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path

import pytest
import pytz
from churchtools_api.churchtools_api import ChurchToolsApi

from church_web_helper.helper import (
    extract_relevant_calendar_appointment_shortname,
    get_primary_resource,
    get_special_day_name,
)

logger = logging.getLogger(__name__)

config_file = Path("logging_config.json")
with config_file.open(encoding="utf-8") as f_in:
    logging_config = json.load(f_in)
    log_directory = Path(logging_config["handlers"]["file"]["filename"]).parent
    if not log_directory.exists():
        log_directory.mkdir(parents=True)
    logging.config.dictConfig(config=logging_config)


class Test_Helper:
    """Combined tests"""

    def setup_method(self) -> None:
        """Init API connection used for all tests"""
        self.ct_api = ChurchToolsApi(
            domain=os.getenv("CT_DOMAIN"), ct_token=os.getenv("CT_TOKEN")
        )

    # Parametrized pytest function
    @pytest.mark.parametrize(
        ("sample_input", "expected_output"),
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
            (
                "10:00 Zentral-Gottesdienst Maki Goldene und Diamantene Konfirmation",
                "Konfirmation",
            ),
        ],
    )
    def test_extract_relevant_calendar_appointment_shortname(
        self, sample_input: str, expected_output: str
    ) -> None:
        """CHeck shortname can be extracted."""
        assert (
            extract_relevant_calendar_appointment_shortname(longname=sample_input)
            == expected_output
        )

    @pytest.mark.parametrize(
        ("date", "expected_output"),
        [
            (
                datetime(year=2024, month=12, day=23, hour=23).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                "",
            ),
            (
                datetime(year=2024, month=12, day=24).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                "Christvesper",
            ),
            (
                datetime(year=2024, month=12, day=25).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                "Christfest I",
            ),
            (
                datetime(year=2024, month=12, day=26).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                "Christfest II",
            ),
            (
                datetime(year=2024, month=12, day=26, hour=23).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                "Christfest II",
            ),
        ],
    )
    def test_get_special_day_name(self, date: datetime, expected_output: str) -> None:
        """Check that special day names can be identified."""

        special_name_calendar_ids = [52, 72]

        assert (
            get_special_day_name(
                ct_api=self.ct_api,
                special_name_calendar_ids=special_name_calendar_ids,
                date=date,
            )
            == expected_output
        )

    def test_get_primary_resource(self) -> None:
        """Check if primary resource can be identified."""
        SAMPLE_EVENT_ID = 330754
        SAMPLE_DATE = datetime(year=2024, month=9, day=29).astimezone(
            pytz.timezone("Europe/Berlin")
        )
        EXPECTED_RESULT = {"Michaelskirche (MIKI)"}
        RESOURCE_IDS = [8, 16, 17, 20, 21]

        result = get_primary_resource(
            appointment_id=SAMPLE_EVENT_ID,
            relevant_date=SAMPLE_DATE,
            ct_api=self.ct_api,
            considered_resource_ids=RESOURCE_IDS,
        )

        assert result == EXPECTED_RESULT
