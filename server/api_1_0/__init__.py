from flask import Blueprint
from flask.ext.restful import Api

# Define a blueprint for this resource
api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint)

from . import experiments, analyses, pipelines, visualizations, plots, tasks, storage_files, users, files, auth, illumina_files

# API Endpoints

# general files resource
api.add_resource(files.FileListController, '/files/')
api.add_resource(files.FileController, '/files/<int:file_id>')
# experiment
api.add_resource(experiments.ExperimentListController, '/experiments/')
api.add_resource(experiments.ExperimentController, '/experiments/<int:experiment_id>')
# experiment-specific files
api.add_resource(experiments.ExperimentFileListController, '/experiments/<int:experiment_id>/files/')
api.add_resource(experiments.ExperimentFileController, '/experiments/<int:experiment_id>/files/<int:file_id>')
# analysis
api.add_resource(analyses.AnalysisListController, '/experiments/<int:experiment_id>/analyses/')
api.add_resource(analyses.AnalysisController, '/experiments/<int:experiment_id>/analyses/<int:analysis_id>')
# pipeline
api.add_resource(pipelines.PipelineListController, '/pipelines/')
api.add_resource(pipelines.PipelineController, '/pipelines/<pipeline_uid>')
# visualization
api.add_resource(visualizations.VisualizationListController, '/experiments/<int:experiment_id>/visualizations/')
api.add_resource(visualizations.VisualizationController, '/experiments/<int:experiment_id>/visualizations/<int:visualization_id>')
# plot
api.add_resource(plots.PlotListController, '/plots/')
api.add_resource(plots.PlotController, '/plots/<plot_uid>')
# task status
api.add_resource(tasks.TaskStatusController, '/taskstatus/<task_id>')
# storage files from preuploads folder
api.add_resource(storage_files.StorageFileListController, '/storage_files/')
# illumina folders and files
api.add_resource(illumina_files.IlluminaFolderListController, '/illumina_folders/')
api.add_resource(illumina_files.IlluminaFolderFileListController, '/illumina_folders/<folder_uid>/files/')

# user
api.add_resource(users.UserListController, '/users/')
api.add_resource(users.UserController, '/users/<user_id>')
# login
api.add_resource(auth.LoginController, '/login/')
