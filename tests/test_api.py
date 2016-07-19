import unittest
import json
import re
from flask import url_for
from server import create_app, db
from server.models import Experiment, ExperimentFile


class APITestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    #------------------------------------------
    # Test cases
    #------------------------------------------

    def test_experiment_list_post(self):
        """Test post request to ExperimentListController"""

        response = self.client.post(url_for('api.experimentlistcontroller'),
                                data=json.dumps({
                                    'exp_type': 'RNA-Seq',
                                    'name':'Experiment X',
                                    'date':'2016-07-18',
                                    'experimenter':'Max Mustermann',
                                    'species':'Mouse',
                                    'tissue': 'Hippocampus'
                                }))
        self.assertEqual(response.status_code, 201)

    def test_experiment_list_get(self):
        """Test get request to ExperimentListController"""

        experiment = Experiment(exp_type='RNA-Seq', name='Experiment X', date='2016-07-18', experimenter='Max Mustermann', species='Mouse', tissue='Hippocampus')
        db.session.add(experiment)
        db.session.commit()


        response = self.client.get(url_for('api.experimentlistcontroller'))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(isinstance(json_response[0].get('id'), int))
        self.assertTrue(json_response[0].get('id') == experiment.id)
        # need to use .isoformat() because the output datetime from postgres DB has a space rather than T to separate the date and time.
        # the json response gets formated the right way (like ISO 8601 specifies, with a T) by flask-restful
        # https://www.postgresql.org/docs/9.2/static/datatype-datetime.html#DATATYPE-DATETIME-OUTPUT-TABLE
        self.assertTrue(json_response[0].get('date_created') == experiment.date_created.isoformat())
        self.assertTrue(json_response[0].get('date_modified') == experiment.date_modified.isoformat())
        self.assertTrue(json_response[0].get('exp_type') == experiment.exp_type)
        self.assertTrue(json_response[0].get('name') == experiment.name)
        self.assertTrue(json_response[0].get('date') == experiment.date)
        self.assertTrue(json_response[0].get('experimenter') == experiment.experimenter)
        self.assertTrue(json_response[0].get('species') == experiment.species)
        self.assertTrue(json_response[0].get('tissue') == experiment.tissue)

    def test_experiment_get(self):
        """Test get request to ExperimentController"""

        experiment = Experiment(exp_type='RNA-Seq', name='Experiment X', date='2016-07-18', experimenter='Max Mustermann', species='Mouse', tissue='Hippocampus')
        db.session.add(experiment)
        db.session.commit()

        response = self.client.get(url_for('api.experimentcontroller', experiment_id=experiment.id))
        self.assertEqual(response.status_code, 200)
        json_response = json.loads(response.data.decode('utf-8'))
        self.assertTrue(isinstance(json_response.get('id'), int))
        self.assertTrue(json_response.get('id') == experiment.id)
        self.assertTrue(json_response.get('date_created') == experiment.date_created.isoformat())
        self.assertTrue(json_response.get('date_modified') == experiment.date_modified.isoformat())
        self.assertTrue(json_response.get('exp_type') == experiment.exp_type)
        self.assertTrue(json_response.get('name') == experiment.name)
        self.assertTrue(json_response.get('date') == experiment.date)
        self.assertTrue(json_response.get('experimenter') == experiment.experimenter)
        self.assertTrue(json_response.get('species') == experiment.species)
        self.assertTrue(json_response.get('tissue') == experiment.tissue)
