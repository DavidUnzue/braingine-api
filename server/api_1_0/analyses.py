#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib.request, urllib.parse, urllib.error, os, werkzeug, magic, json
from flask import abort, make_response, current_app, request, g
from flask.ext.restful import Resource, reqparse
from .auth import auth
# Import db instance
from .. import db
# Import models from models.py file
# IMPORTANT!: this has to be done after the DB gets instantiated and in this case imported too
from ..models.collection import Collection
from ..models.file import ExperimentFile, ExperimentFileSchema
from ..models.analysis import Analysis, AnalysisSchema, AnalysisParameter, AssociationAnalysesInputFiles, AssociationAnalysesOutputFiles
from ..models.pipeline import Pipeline, PipelineSchema, PipelineInput, PipelineOutput
from ..utils import sha256checksum, create_folder
# http://stackoverflow.com/a/30399108
from . import api, tasks
# celery task
from ..tasks import run_analysis
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields
from webargs.flaskparser import use_args

analysis_schema = AnalysisSchema()
pipeline_schema = PipelineSchema()
experiment_file_schema = ExperimentFileSchema()


class AnalysisListController(Resource):
    decorators = [auth.login_required]

    def get(self):
        experiment_analyses = Analysis.query.filter_by(user_id=g.user.id).all()
        result = analysis_schema.dump(experiment_analyses, many=True).data
        return result, 200

    def get_pipeline_checksum(self, pipeline_uid):
        return sha256checksum(self.get_pipeline_definition_file(pipeline_uid))

    def get_pipeline_definition_file(self, pipeline_uid):
        """
        Build filename for given pipeline
        """
        pipeine_definition_file_path = os.path.join(current_app.config.get('PIPELINES_FOLDER'), pipeline_uid, '{}.json'.format(pipeline_uid))
        return pipeine_definition_file_path

    def load_pipeline_definition(self, pipeline_uid):
        """
        Serializes fields from a JSON pipeline definition file into a dictionary
        """
        with open(self.get_pipeline_definition_file(pipeline_uid)) as pipeline_definition_file:
            pipeline_definition = json.load(pipeline_definition_file)
            pipeline_definition_dict = pipeline_schema.load(pipeline_definition).data
        return pipeline_definition_dict

    def store_pipeline(self, pipeline_uid):
        # serialize pipeline definition file
        pipeline_definition = self.load_pipeline_definition(pipeline_uid)

        # get needed pipeline fields
        pipeline_uid = pipeline_definition['uid']
        pipeline_filename = pipeline_definition['filename']
        pipeline_name = pipeline_definition['name']
        pipeline_description = pipeline_definition['description']
        pipeline_executor = pipeline_definition['executor']
        pipeline_command = pipeline_definition['command']
        pipeline_inputs = pipeline_definition['inputs']
        pipeline_outputs = pipeline_definition['outputs']

        pipeline_checksum = self.get_pipeline_checksum(pipeline_uid)

        # create pipeline object
        pipeline = Pipeline(uid=pipeline_uid, filename=pipeline_filename, name=pipeline_name, description=pipeline_description, executor=pipeline_executor, command=pipeline_command, checksum=pipeline_checksum)

        # add inputs and outputs relationschips
        for pipeline_input in pipeline_inputs:
            pipeline.inputs.append(PipelineInput(name=pipeline_input['name'],label=pipeline_input['label'],help=pipeline_input['help'],type=pipeline_input['type'],multiple=pipeline_input['multiple'],format=pipeline_input['format']))
        for pipeline_output in pipeline_outputs:
            pipeline.outputs.append(PipelineOutput(name=pipeline_output['name'],label=pipeline_output['label'],type=pipeline_output['type'],value=pipeline_output['value'],format=pipeline_output['format']))

        # add to database
        db.session.add(pipeline)
        db.session.commit()

        return pipeline

    def update_pipeline(self, pipeline_object):
        """
        Updates a pipeline object retrieved from DB with new attribute values
        """
        pipeline_id = pipeline_object.uid
        # load pipeline definition json
        pipeline_definition_dict = self.load_pipeline_definition(pipeline_id)

        pipeline_checksum = self.get_pipeline_checksum(pipeline_id)

        # remove and add attributes needed to update DB entry
        del pipeline_definition_dict['inputs']
        del pipeline_definition_dict['outputs']
        pipeline_definition_dict.update(dict(checksum=pipeline_checksum))

        # iterate and update each attribute
        for key, value in pipeline_definition_dict.items():
            if value is not None:
                # check if pipeline object has the current attribute and update it
                # we want to avoid definition files injecting new non-existent object attributes
                current_attr = getattr(pipeline_object, key, None)
                if current_attr is not None:
                    setattr(pipeline_object, key, value)

        db.session.commit()

    @use_args(analysis_schema)
    def post(self, args):
        from string import Template

        user = g.user
        pipeline_uid = args['pipeline_uid']
        # get pipeline from DB
        pipeline = Pipeline.query.filter_by(uid=pipeline_uid).first()
        # if pipeline not available in DB or checksum of definition file changed, create new DB entry
        if pipeline is None or (pipeline.checksum != self.get_pipeline_checksum(pipeline_uid)):
            pipeline = self.store_pipeline(pipeline_uid)

        # =====
        # GET PIPELINE PARAMETERS
        # =====

        # merge parameter dictionaries (key-value pairs) into one single dictionary, in order to work on Template.substitute
        input_parameters = {d['name']: d['value'] for d in args['parameters']}

        pipeline_input_files = {}
        for pi in pipeline.inputs:
            if pi.type == "file":
                pipeline_input_files[pi.name] = ""
        pipeline_output_files = {}
        for po in pipeline.outputs:
            pipeline_output_files[po.name.strip(os.sep)] = po.value

        # =====
        # CREATE DB ENTRIES FOR NEW ANALYSIS
        # =====

        # create analysis entity
        experiment_analysis = Analysis(user_id=user.id, pipeline_id=pipeline.id, pipeline_uid=pipeline_uid)
        # add analysis to DB
        db.session.add(experiment_analysis)
        # flush to let DB create id primary key for experiment_analysis
        db.session.flush()
        # add DB entries for parameters for the analysis created before
        for param_name, param_value in input_parameters.items():
            # look for input files
            if param_name in pipeline_input_files:
                file_paths = []
                # add input files to analysis-file relationship
                for file_id in param_value.split(','):
                    # create association object
                    analysis_input_file_assoc = AssociationAnalysesInputFiles(pipeline_fieldname=param_name)
                    # get object for current file from input files
                    input_file = ExperimentFile.query.get(file_id)
                    # add file to analysis
                    analysis_input_file_assoc.input_file = input_file
                    experiment_analysis.input_files.append(analysis_input_file_assoc)
                    # store file's path for each input file
                    input_file_path = input_file.path
                    file_paths.append(input_file_path)
                # include file paths for each param for later use in command building
                pipeline_input_files[param_name] = ' '.join(file_paths)
            else:
                analysis_parameter = AnalysisParameter(analysis_id=experiment_analysis.id, name=param_name, value=param_value)
                db.session.add(analysis_parameter)
        # add parameters to DB
        db.session.commit()

        # update parameters dict to include file paths instead of file ids
        input_parameters.update(pipeline_input_files)


        # =====
        # CREATE ANALYSIS OUTPUT FOLDER
        # =====
        create_folder(os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), user.username, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id)))


        # =====
        # CREATE AND SEND COMMAND TO BE EXECUTED
        # =====

        # build folder paths for the remote command
        # notice that the paths here are relative to the computing server and not to the web server
        experiment_folder = os.path.join(current_app.config.get('DATA_STORAGE'), user.username)
        analysis_folder = os.path.join(experiment_folder, current_app.config.get('ANALYSES_FOLDER'), str(experiment_analysis.id))

        # write params into command template
        pipeline_command = Template(pipeline.command)
        pipeline_command_parameters = pipeline_command.substitute(input_parameters, **pipeline_output_files)

        pipeline_file_path = os.path.join(current_app.config.get('PIPELINES_STORAGE'), pipeline.uid, pipeline.filename)
        final_pipeline_command = '{} {} {}'.format(pipeline.executor, pipeline_file_path, pipeline_command_parameters)

        # remote command should first change directory to experiment folder, then execute the pipeline command
        remote_command = 'cd {}; {}'.format(analysis_folder, final_pipeline_command)

        # send task to celery and store it in a variable for returning task id in location header
        task = run_analysis.delay(remote_command, pipeline_id=pipeline.id, analysis_id=experiment_analysis.id, analysis_outputs=pipeline_output_files)

        # =====
        # RETURN CREATED ANALYSIS INSTANCE AND TASK STATUS URL
        # =====

        result = analysis_schema.dump(experiment_analysis).data

        return result, 202, {'Location': api.url_for(tasks.TaskStatusController, task_id=task.id)}


class AnalysisController(Resource):
    decorators = [auth.login_required]

    def get(self, analysis_id):
        experiment_analysis = Analysis.query.get(analysis_id)
        result = analysis_schema.dump(experiment_analysis).data
        return result, 200

    def delete(self, analysis_id):
        experiment_analysis = Analysis.query.get(analysis_id)
        if not experiment_analysis:
            abort(404, "Analysis {} for experiment {} doesn't exist".format(experiment_id, analysis_id))
        db.session.delete(experiment_analysis)
        db.session.commit()
        return {}, 204

    @use_args(analysis_schema)
    def put(self, args, analysis_id):
        experiment_analysis = Analysis.query.get(analysis_id)
        if not experiment_analysis:
            abort(404, "Experiment analysis {} doesn't exist".format(analysis_id))
        for k, v in list(args.items()):
            if v is not None:
                setattr(experiment_analysis, k, v)
        db.session.add(experiment_analysis)
        db.session.commit()
        result = analysis_schema.dump(experiment_analysis).data
        return result, 200


class AnalysisInputFileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'page': fields.Int(missing=1)
    })
    def get(self, args, analysis_id):
        # pagination
        page = args['page']

        file_ids = AssociationAnalysesInputFiles.query \
                    .with_entities(AssociationAnalysesInputFiles.file_id) \
                    .filter_by(analysis_id=analysis_id).all()

        pagination = ExperimentFile.query \
                        .filter(ExperimentFile.id.in_(file_ids)) \
                        .paginate(page, current_app.config.get('ITEMS_PER_PAGE'), False)

        files = pagination.items

        page_prev = None
        if pagination.has_prev:
            page_prev = api.url_for(self, page=page-1, _external=True)
        page_next = None
        if pagination.has_next:
            page_next = api.url_for(self, page=page+1, _external=True)

        result = experiment_file_schema.dump(files, many=True).data

        return result, 200


class AnalysisOutputFileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'page': fields.Int(missing=1)
    })
    def get(self, args, analysis_id):
        # pagination
        page = args['page']

        file_ids = AssociationAnalysesOutputFiles.query \
                    .with_entities(AssociationAnalysesOutputFiles.file_id) \
                    .filter_by(analysis_id=analysis_id).all()

        pagination = ExperimentFile.query \
                        .filter(ExperimentFile.id.in_(file_ids)) \
                        .paginate(page, current_app.config.get('ITEMS_PER_PAGE'), False)

        files = pagination.items

        page_prev = None
        if pagination.has_prev:
            page_prev = api.url_for(self, page=page-1, _external=True)
        page_next = None
        if pagination.has_next:
            page_next = api.url_for(self, page=page+1, _external=True)

        result = experiment_file_schema.dump(files, many=True).data

        return result, 200
