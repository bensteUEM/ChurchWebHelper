import ast
import logging
import os
import unittest
from datetime import datetime, timedelta

from ChurchToolsApi import ChurchToolsApi


class TestsChurchWebHelper(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestsChurchWebHelper, self).__init__(*args, **kwargs)

        if 'CT_TOKEN' in os.environ:
            self.ct_token = os.environ['CT_TOKEN']
            self.ct_domain = os.environ['CT_DOMAIN']
            users_string = os.environ['CT_USERS']
            self.ct_users = ast.literal_eval(users_string)
            logging.info('using connection details provided with ENV variables')
        else:
            from secure.config import ct_token
            self.ct_token = ct_token
            from secure.config import ct_domain
            self.ct_domain = ct_domain
            from secure.config import ct_users
            self.ct_users = ct_users
            logging.info('using connection details provided from secrets folder')

        self.api = ChurchToolsApi(domain=self.ct_domain, ct_token=self.ct_token)
        logging.basicConfig(filename='logs/TestsChurchToolsApi.log', encoding='utf-8',
                            format="%(asctime)s %(name)-10s %(levelname)-8s %(message)s",
                            level=logging.DEBUG)
        logging.info("Executing Tests RUN")

    def tearDown(self):
        """
        Destroy the session after test execution to avoid resource issues
        :return:
        """
        self.api.session.close()

    def test_dummy(self):
        """
        Tries to create a login with churchTools using specified username and password
        :return:
        """
        self.assertTrue(True,'Tests not implemented yet')