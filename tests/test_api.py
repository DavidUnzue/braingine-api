import unittest, pprint
import json
import re
from flask import url_for
from server import create_app, db
from server.models import Experiment, ExperimentFile


class TestRequestsToExperiments(unittest.TestCase):
    """Test api requests to experiments"""

    def setUp(self):
        """On tests start"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()
        # populate database
        self._init_data()

    def tearDown(self):
        """On tests end"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _init_data(self):
        """Populate database with sample data"""
        # add sample experiment to database
        self.sampleExperimentData = dict(exp_type='RNA-Seq', name='Experiment X', date='2016-07-18', experimenter='Max Mustermann', species='Mouse', tissue='Hippocampus')
        self.sampleExperiment = Experiment(**self.sampleExperimentData)
        db.session.add(self.sampleExperiment)
        db.session.commit()

    def json_response(self, response):
        """Return data of a json response"""
        json_response = json.loads(response.data.decode('utf-8'))
        return json_response

    def test_get_experiment_list(self):
        """Test get request to ExperimentListController"""

        experiment = self.sampleExperiment

        # make http get call
        response = self.client.get(url_for('api.experimentlistcontroller'))
        self.assertEqual(response.status_code, 200)
        json_response = self.json_response(response)
        # should return a non-empty list with the experiment added before to the DB
        self.assertTrue(len(json_response) > 0)
        # every attribute should be exactly the same as those added to the DB
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

    def test_post_experiment_list(self):
        """Test post request to ExperimentListController"""

        experiment = self.sampleExperimentData
        # make http post call with attributes
        response = self.client.post(url_for('api.experimentlistcontroller'),
                                data=experiment)
        # status code should be 201 okay
        self.assertEqual(response.status_code, 201)

    def test_get_experiment(self):
        """Test get request to ExperimentController"""

        experiment = self.sampleExperiment

        response = self.client.get(url_for('api.experimentcontroller', experiment_id=experiment.id))
        self.assertEqual(response.status_code, 200)
        json_response = self.json_response(response)
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

    def test_get_nonexistent_experiment(self):
        """Test get request for a non-existent experiment"""

        response = self.client.get(url_for('api.experimentcontroller', experiment_id=1000))
        self.assertEqual(response.status_code, 404)

    def test_delete_experiment(self):
        """Test delete request to ExperimentController"""

        experiment = self.sampleExperiment

        response = self.client.delete(url_for('api.experimentcontroller', experiment_id=experiment.id))
        self.assertEqual(response.status_code, 204)

    def test_delete_nonexistent_experiment(self):
        """Test delete request for a non-existent experiment"""

        response = self.client.delete(url_for('api.experimentcontroller', experiment_id=1000))
        self.assertEqual(response.status_code, 404)
