"""All tests in regards to test_export_xlsx.py."""

import json
import logging
import logging.config
import os
from pathlib import Path

import pytest
from churchtools_api.churchtools_api import ChurchToolsApi

from church_web_helper.export_xlsx import get_plan_months_xlsx  # noqa: F401

logger = logging.getLogger(__name__)

config_file = Path("logging_config.json")
with config_file.open(encoding="utf-8") as f_in:
    logging_config = json.load(f_in)
    log_directory = Path(logging_config["handlers"]["file"]["filename"]).parent
    if not log_directory.exists():
        log_directory.mkdir(parents=True)
    logging.config.dictConfig(config=logging_config)


class Test_Helper:
    """Combined tests."""

    def setup_method(self) -> None:
        """Init API connection used for all tests."""
        self.ct_api = ChurchToolsApi(
            domain=os.getenv("CT_DOMAIN"), ct_token=os.getenv("CT_TOKEN")
        )

    @pytest.mark.skip("No export test implemented")
    def get_plan_months_xlsx(self) -> None:
        """Dummy placeholder for possible tests."""
        pass
        # get_plan_months_xlsx()  # noqa: ERA001
