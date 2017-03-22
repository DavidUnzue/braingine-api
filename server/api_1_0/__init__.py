from flask import Blueprint
from flask.ext.restful import Api

# Define a blueprint for this resource
api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

from . import experiments, pipelines, tasks, storage_files

# API Endpoints

# experiment
api.add_resource(experiments.ExperimentListController, '/experiments/')
api.add_resource(experiments.ExperimentController, '/experiments/<int:experiment_id>')
api.add_resource(experiments.ExperimentFileListController, '/experiments/<int:experiment_id>/files/')
api.add_resource(experiments.ExperimentFileController, '/experiments/<int:experiment_id>/files/<int:file_id>')
# analysis
api.add_resource(experiments.AnalysisListController, '/experiments/<int:experiment_id>/analyses/')
api.add_resource(experiments.AnalysisController, '/experiments/<int:experiment_id>/analyses/<int:analysis_id>')
# pipeline
api.add_resource(pipelines.PipelineListController, '/pipelines/')
api.add_resource(pipelines.PipelineController, '/pipelines/<pipeline_filename>')
# task status
api.add_resource(tasks.TaskStatusController, '/taskstatus/<task_id>')
# storage files from preuploads folder
api.add_resource(storage_files.StorageFileListController, '/storage_files/')
