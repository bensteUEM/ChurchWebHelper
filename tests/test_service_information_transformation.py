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

from church_web_helper.service_information_transformation import (
    get_group_name_services,
    get_group_title_of_person,
    get_service_assignment_lastnames_or_unknown,
    get_title_name_services,
    replace_special_services_with_service_shortnames,
)

logger = logging.getLogger(__name__)

config_file = Path("logging_config.json")
with config_file.open(encoding="utf-8") as f_in:
    logging_config = json.load(f_in)
    log_directory = Path(logging_config["handlers"]["file"]["filename"]).parent
    if not log_directory.exists():
        log_directory.mkdir(parents=True)
    logging.config.dictConfig(config=logging_config)


class TestServiceInformationTransformation:
    """Combined tests that require API access."""

    def setup_method(self) -> None:
        """Init API connection used for all tests."""
        self.ct_api = ChurchToolsApi(
            domain=os.getenv("CT_DOMAIN"), ct_token=os.getenv("CT_TOKEN")
        )

    @pytest.mark.parametrize(
        ("person_id", "relevant_groups", "expected_result"),
        [
            (51, [367, 89, 355, 358], "Pfarrer"),
            (51, [], ""),
            (822, [367, 89, 355, 358], "Pfarrerin"),
            (110, [367, 89, 355, 358], "Prädikant"),
            (205, [367, 89, 355, 358], "Pfarrer i.R."),
            (911, [367, 89, 355, 358], "Pfarrerin i.R."),
            (423, [370], "Pastoralreferent (Kath.)"),
            (420, [370], "Pastoralreferentin (Kath.)"),
            (513, [355, 358], ""),
            (640, [358], "Diakon"),
        ],
    )
    def test_get_group_title_of_person(
        self, person_id: int, relevant_groups: list[int], expected_result: str
    ) -> None:
        """Check that titles by group can be retrieved.

        ELKW1610 specific IDs -
        """
        result = get_group_title_of_person(
            person_id,
            relevant_groups,
            api=self.ct_api,
        )
        assert expected_result == result

    # ELKW1610 specific IDs
    # 331510 - Musikteam 23.3.25 GH
    # 331150 - Kirchenchor 30.3.25 GH 10:00
    # 331153 - InJoyChor 14.12 - 10:00
    # 331153 - PChor - 4.5.25
    @pytest.mark.parametrize(
        ("appointment_id", "relevant_date", "considered_services", "expected_result"),
        [
            (
                331510,
                datetime(year=2025, month=3, day=23).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                [9, 61],
                "",
            ),
            (
                331150,
                datetime(year=2025, month=3, day=30).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                [9, 61],
                "mit Kirchenchor",
            ),
            (
                331150,
                datetime(year=2025, month=3, day=30).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                [],
                "",
            ),
            # Testing "mit InJoy Chor
            (
                331153,
                datetime(year=2025, month=12, day=14).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                [9, 61],
                "mit InJoy Chor",
            ),
            # Testing "mit Kirchenchor
            (
                331153,
                datetime(year=2025, month=5, day=4).astimezone(
                    pytz.timezone("Europe/Berlin")
                ),
                [9, 61],
                "mit Posaunenchor",
            ),
        ],
    )
    def test_get_group_name_services(
        self,
        appointment_id: int,
        relevant_date: datetime,
        considered_services: list[int],
        expected_result: str,
    ) -> None:
        """Check that special service group names can be retrieved.

        ELKW1610 specific IDs -
        """
        SAMPLE_CALENDAR_IDS = [2]
        SAMPLE_GROUPTYPE_ROLE_ID_LEADS = [9, 16]

        result = get_group_name_services(
            calendar_ids=SAMPLE_CALENDAR_IDS,
            appointment_id=appointment_id,
            relevant_date=relevant_date,
            api=self.ct_api,
            considered_music_services=considered_services,
            considered_grouptype_role_ids=SAMPLE_GROUPTYPE_ROLE_ID_LEADS,
        )

        assert expected_result == result

    def test_get_title_name_services(self) -> None:
        """Check respective function with real sample.

        IMPORTANT - This test method and the parameters used depend on target system!
        The sample event needs to be less than 3 months old
        otherwise it will not be available
        On ELKW1610.KRZ.TOOLS event ID 331144 is an existing event
        """
        SAMPLE_CALENDAR_IDS = [2]
        SAMPLE_APPOINTMENT_ID = 331144
        SAMPLE_DATE = datetime(year=2025, month=1, day=1).astimezone(
            pytz.timezone("Europe/Berlin")
        )
        SAMPLE_SERVICES = [1]
        SAMPLE_GROUPS_FOR_PREFIX = [89, 355, 358, 361, 367, 370, 373]

        result = get_title_name_services(
            calendar_ids=SAMPLE_CALENDAR_IDS,
            appointment_id=SAMPLE_APPOINTMENT_ID,
            relevant_date=SAMPLE_DATE,
            considered_program_services=SAMPLE_SERVICES,
            considered_groups=SAMPLE_GROUPS_FOR_PREFIX,
            api=self.ct_api,
        )

        EXPECTED_RESULT = "Pfarrer Raiser"
        assert result == EXPECTED_RESULT

    @pytest.mark.parametrize(
        ("service_name", "event_id", "expected_result"),
        [
            ("musikteam", 4033, "Kulajew"),
            ("musikteam", 4042, "Finkbeiner"),
            ("taufe", 4030, "Leandra Caluser"),
            ("organist", 4036, "Dilper"),
            ("organist", 4033, "Hornung"),
            ("musikteam", 4036, "Mohr")
        ],
    )
    def test_get_service_assignment_lastnames_or_unknown(
        self, service_name: str, event_id: int, expected_result: str
    ) -> None:
        """Check respective function with real samples.

        IMPORTANT - This test method and the parameters used depend on target system!
        On ELKW1610.KRZ.TOOLS above parametrized events
            and service assignements in early 2025 exist

        Arguments:
            service_name: readable lower_case name of the service
            event_id: the event to check
            expected_result: comapre result
        """
        DEFAULTS = {
            "default_timeframe_months": 1,
            "special_day_calendar_ids": [52, 72],
            "selected_calendars": [2],
            "available_resource_type_ids": [4, 6, 5],
            "selected_resources": [8, 20, 21, 16, 17],
            "selected_program_services": [1],
            "selected_title_prefix_groups": [89, 355, 358, 361, 367, 370, 373],
            "selected_music_services": [9, 61],
            "grouptype_role_id_leads": [
                9,  # Leitung in "Dienst"
                16,  # Leitung in "Kleingruppe"
            ],
            "program_service_group_id": 1,
            "music_service_group_ids": [4],
            "predigt_service_ids": [1],
            "organist_service_ids": [2, 87],
            "musikteam_service_ids": [10],
            "taufe_service_ids": [127],
            "abendmahl_service_ids": [100],
        }
        result = get_service_assignment_lastnames_or_unknown(
            ct_api=self.ct_api,
            service_name=service_name,
            event_id=event_id,
            config=DEFAULTS,
        )
        assert expected_result == result


@pytest.mark.parametrize(
    ("sample_value", "expected_result"),
    [
        ("mit Posaunenchor", "Pos.Chor"),
        ("mit Kirchenchor", "Kir.Chor"),
        ("mit InJoy Chor", "InJ.Chor"),
        ("mit InJoy Chor und Kirchenchor", "InJ.Chor, Kir.Chor"),
        ("mit Posaunenchor und Kirchenchor", "Pos.Chor, Kir.Chor"),
        ("mit Was anderes", "Was anderes"),
    ],
)
def test_replace_special_services_with_service_shortnames(
    sample_value: str, expected_result: str
) -> None:
    """Paramized test which checks for intended replacements."""
    assert (
        replace_special_services_with_service_shortnames(special_services=sample_value)
        == expected_result
    )
