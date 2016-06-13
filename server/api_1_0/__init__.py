from flask import Blueprint
from flask.ext.restful import Api

# Define a blueprint for this resource
api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

from . import experiments

# API Endpoints
api.add_resource(experiments.ExperimentListController, '/experiments/')
api.add_resource(experiments.ExperimentController, '/experiments/<int:experiment_id>')
api.add_resource(experiments.ExperimentFileListController, '/experiments/<int:experiment_id>/files/')
api.add_resource(experiments.ExperimentFileController, '/experiments/<int:experiment_id>/files/<int:file_id>')
api.add_resource(experiments.ExperimentAnalysisController, '/experiments/<int:experiment_id>/analysis/')
