#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib.request, urllib.parse, urllib.error, os, werkzeug, magic, json, subprocess
from flask import abort, make_response, current_app, request, g
from flask.ext.restful import Resource, reqparse
from .auth import auth
# Import db instance
from .. import db
# Import models from models.py file
# IMPORTANT!: this has to be done after the DB gets instantiated and in this case imported too
from ..models.experiment import Experiment, ExperimentFile, Visualization, VisualizationSchema, VisualizationParameter, AssociationVisualizationsInputFiles
from ..models.plot import Plot, PlotSchema, PlotInput
from ..utils import sha256checksum, create_folder
# http://stackoverflow.com/a/30399108
from . import api, tasks
# celery task
from ..tasks import create_visualization
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields
from webargs.flaskparser import use_args

visualization_schema = VisualizationSchema()


class VisualizationListController(Resource):
    decorators = [auth.login_required]

    def _get_plot_checksum(self, plot_uid):
        return sha256checksum(self._get_plot_definition_file(plot_uid))

    def _get_plot_definition_file(self, plot_uid):
        """
        Build filename for given plot
        """
        return '{}/{}.json'.format(current_app.config.get('PLOTS_FOLDER'), plot_uid)

    def _load_plot_definition(self, plot_uid):
        """
        Serializes fields from a JSON plot definition file into a dictionary
        """
        with open(self._get_plot_definition_file(plot_uid)) as plot_definition_file:
            plot_definition = json.load(plot_definition_file)
        return plot_definition

    def _store_plot(self, plot_uid):
        # serialize plot definition file
        plot_definition = self._load_plot_definition(plot_uid)

        # get needed plot fields
        plot_uid = plot_definition['uid']
        plot_filename = plot_definition['filename']
        plot_name = plot_definition['name']
        plot_description = plot_definition['description']
        plot_executor = plot_definition['executor']
        plot_command = plot_definition['command']
        plot_inputs = plot_definition['inputs']
        plot_output_file_name = plot_definition['output_file_name']

        plot_checksum = self._get_plot_checksum(plot_uid)

        # create plot object
        plot = Plot(uid=plot_uid, filename=plot_filename, name=plot_name, description=plot_description, executor=plot_executor, command=plot_command, checksum=plot_checksum, output_filename=plot_output_file_name)

        # add inputs and outputs relationschips
        for plot_input in plot_inputs:
            plot.inputs.append(PlotInput(name=plot_input['name'],label=plot_input['label'],help=plot_input['help'],type=plot_input['type'],multiple=plot_input['multiple'],format=plot_input['format'], required=plot_input['required']))

        # add to database
        db.session.add(plot)
        db.session.commit()

        return plot

    def get(self, experiment_id):
        experiment_visualizations = Visualization.query.filter_by(experiment_id=experiment_id).all()
        result = visualization_schema.dump(experiment_visualizations, many=True).data
        return result, 200

    @use_args(visualization_schema)
    def post(self, args, experiment_id):
        from string import Template

        plot_uid = args['plot_uid']
        experiment = Experiment.query.get(experiment_id)

        # get plot from DB
        plot = Plot.query.filter_by(uid=plot_uid).first()
        # if plot not available in DB or checksum of definition file changed, create new DB entry
        if plot is None or (plot.checksum != self._get_plot_checksum(plot_uid)):
            plot = self._store_plot(plot_uid)

        # =====
        # GET PLOT PARAMETERS
        # =====

        # merge parameter dictionaries (key-value pairs) into one single dictionary, in order to work on Template.substitute
        input_parameters = {d['name']: d['value'] for d in args['parameters']}

        plot_input_files = {}
        for pi in plot.inputs:
            if pi.type == "file":
                plot_input_files[pi.name] = ""

        # =====
        # CREATE DB ENTRIES FOR NEW VISUALIZATION
        # =====

        # create visualization entity
        experiment_visualization = Visualization(experiment_id=experiment_id, plot_id=plot.id, plot_uid=plot_uid)
        # add analysis to DB
        db.session.add(experiment_visualization)
        # flush to let DB create id
        db.session.flush()
        # add DB entries for parameters for the analysis created before
        for param_name, param_value in input_parameters.items():
            # look for input files
            if param_name in plot_input_files:
                file_paths = []
                # add input files to visualization-file relationship
                for file_id in param_value.split(','):
                    # create association object
                    visualization_input_file_assoc = AssociationVisualizationsInputFiles(plot_fieldname=param_name)
                    # get object for current file from input files
                    input_file = ExperimentFile.query.get(file_id)
                    # add file to visualization
                    visualization_input_file_assoc.input_file = input_file
                    experiment_visualization.input_files.append(visualization_input_file_assoc)
                    # store file's path for each input file
                    input_file_path = os.path.join(current_app.config.get('DATA_ROOT_EXTERNAL'), input_file.path)
                    file_paths.append(input_file_path)
                # include file paths for each param for later use in command building
                plot_input_files[param_name] = ' '.join(file_paths)
            else:
                visualization_parameter = VisualizationParameter(visualization_id=experiment_visualization.id, name=param_name, value=param_value)
                db.session.add(visualization_parameter)
        # add parameters to DB
        db.session.commit()

        # update parameters dict to include file paths instead of file ids
        input_parameters.update(plot_input_files)


        # =====
        # CREATE VISUALIZATION OUTPUT FOLDER
        # =====
        create_folder(os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), experiment.sha, current_app.config.get('VISUALIZATIONS_FOLDER'), str(experiment_visualization.id)))


        # =====
        # CREATE AND SEND COMMAND TO BE EXECUTED
        # =====

        # build folder paths for the remote command
        # notice that the paths here are relative to the computing server and not to the web server
        experiment_folder = os.path.join(current_app.config.get('DATA_STORAGE'), experiment.sha)
        visualization_folder = os.path.join(experiment_folder, current_app.config.get('VISUALIZATIONS_FOLDER'), str(experiment_visualization.id))

        # write params into command template
        plot_command = Template(plot.command)
        plot_command_with_parameters = plot_command.substitute(input_parameters)

        plot_file_path = os.path.join(current_app.config.get('PLOTS_STORAGE'), plot.filename)
        final_plot_command = '{} {}'.format(plot.executor, plot_command_with_parameters)

        # remote command should first change directory to visualization folder, then execute the plot command
        remote_command = 'cd {}; {}'.format(visualization_folder, final_plot_command)

        # send task to celery and store it in a variable for returning task id in location header
        task = create_visualization.delay(remote_command, plot_id=plot.id, visualization_id=experiment_visualization.id)

        result = visualization_schema.dump(experiment_visualization).data

        return result, 202, {'Location': api.url_for(tasks.TaskStatusController, task_id=task.id)}


class VisualizationController(Resource):
    decorators = [auth.login_required]

    def get(self, experiment_id, visualization_id):
        experiment_visualization = Visualization.query.filter_by(experiment_id=experiment_id, id=visualization_id).first()
        result = visualization_schema.dump(experiment_visualization).data
        return result, 200

    def delete(self, experiment_id, visualization_id):
        experiment_visualization = Visualization.query.filter_by(experiment_id=experiment_id, id=visualization_id).first()
        if not experiment_visualization:
            abort(404, "Visualization {} for experiment {} doesn't exist".format(experiment_id, visualization_id))
        db.session.delete(experiment_visualization)
        db.session.commit()
        return {}, 204

    @use_args(visualization_schema)
    def put(self, args, experiment_id, visualization_id):
        experiment_visualization = Visualization.query.filter_by(experiment_id=experiment_id, id=visualization_id).first()
        if not experiment_visualization:
            abort(404, "Visualization {} for experiment {} doesn't exist".format(experiment_id, visualization_id))
        for k, v in list(args.items()):
            if v is not None:
                setattr(experiment_visualization, k, v)
        db.session.add(experiment_visualization)
        db.session.commit()
        result = visualization_schema.dump(experiment_visualization).data
        return result, 200
