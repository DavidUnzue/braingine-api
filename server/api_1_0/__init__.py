from flask import Blueprint
from flask.ext.restful import Api

# Define a blueprint for this resource
api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

from . import experiments, analyses, pipelines, visualizations, plots, tasks, storage_files, users

# API Endpoints

# experiment
api.add_resource(experiments.ExperimentListController, '/experiments/')
api.add_resource(experiments.ExperimentController, '/experiments/<int:experiment_id>')
api.add_resource(experiments.ExperimentFileListController, '/experiments/<int:experiment_id>/files/')
api.add_resource(experiments.ExperimentFileController, '/experiments/<int:experiment_id>/files/<int:file_id>')
# analysis
api.add_resource(analyses.AnalysisListController, '/experiments/<int:experiment_id>/analyses/')
api.add_resource(analyses.AnalysisController, '/experiments/<int:experiment_id>/analyses/<int:analysis_id>')
# pipeline
api.add_resource(pipelines.PipelineListController, '/pipelines/')
api.add_resource(pipelines.PipelineController, '/pipelines/<pipeline_filename>')
# visualization
api.add_resource(visualizations.VisualizationListController, '/experiments/<int:experiment_id>/visualizations/')
api.add_resource(visualizations.VisualizationController, '/experiments/<int:experiment_id>/visualizations/<int:visualization_id>')
# plot
api.add_resource(plots.PlotListController, '/plots/')
api.add_resource(plots.PlotController, '/plots/<plot_filename>')
# task status
api.add_resource(tasks.TaskStatusController, '/taskstatus/<task_id>')
# storage files from preuploads folder
api.add_resource(storage_files.StorageFileListController, '/storage_files/')
# user
api.add_resource(users.UserListController, '/users/')
api.add_resource(users.UserController, '/users/<user_id>')
