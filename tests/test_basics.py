import unittest
from flask import current_app
from server import create_app, db


class BasicsTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        """Test if the flask application exists"""
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        """Test if the application is using the testing configuration"""
        self.assertTrue(current_app.config['TESTING'])
