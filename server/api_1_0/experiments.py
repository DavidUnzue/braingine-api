#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, os, werkzeug
from flask import abort, make_response, current_app
from flask.ext.restful import Resource, reqparse
# Import db instance
from server import db
# Import models from models.py file
# IMPORTANT!: this has to be done after the DB gets instantiated and in this case imported too
from server.models import Experiment, ExperimentSchema, ExperimentFile, ExperimentFileSchema, ExperimentAnalysis, ExperimentAnalysisSchema
from server.utils import sha1_string
# http://stackoverflow.com/a/30399108
from . import api, tasks
# celery task
from server.tasks import execute_command
# allow use of or syntax for sql queries
from sqlalchemy import or_
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields, validate
from webargs.flaskparser import parser as webargs_parser, use_args

experiment_schema = ExperimentSchema()
experiment_file_schema = ExperimentFileSchema()
experiment_analysis_schema = ExperimentAnalysisSchema()

parser = reqparse.RequestParser()
# The default argument type is a unicode string. This will be str in python3 and unicode in python2.
parser.add_argument('exp_type', location=['form', 'json'])
parser.add_argument('name', location=['form', 'json'])
parser.add_argument('date', location=['form', 'json'])
parser.add_argument('experimenter', location=['form', 'json'])
parser.add_argument('species', location=['form', 'json'])
parser.add_argument('tissue', location=['form', 'json'])
parser.add_argument('information', location=['form', 'json'])
parser.add_argument('files[]', action='append', type=werkzeug.datastructures.FileStorage, location=['files'])
parser.add_argument('Content-Range', location=['headers'])
parser.add_argument('q', location=['args'])


class ExperimentListController(Resource):
    def get(self):
        parser.add_argument('page', type=int, default=1, location=['args'])
        parsed_args = parser.parse_args()
        page = parsed_args['page']
        if parsed_args['q']:
            # querystring from url should be decoded here
            # see https://unspecified.wordpress.com/2008/05/24/uri-encoding/
            #search_query = urllib.unquote(parsed_args['q']).decode("utf-8")
            search_query = urllib.unquote(parsed_args['q'])
            # search for experiments containing the search query in their "name" or "experimenter" attributes
            # use "ilike" for searching case unsensitive
            experiments = Experiment.query.filter(or_(Experiment.name.ilike('%'+ search_query + '%'), Experiment.experimenter.ilike('%'+ search_query + '%'), Experiment.exp_type.ilike('%'+ search_query + '%'), Experiment.species.ilike('%'+ search_query + '%'), Experiment.tissue.ilike('%'+ search_query + '%'))).all()
        else:
            pagination = Experiment.query.paginate(page, 5)
            experiments = pagination.items
            #experiments = Experiment.query.all()
            page_prev = None
            if pagination.has_prev:
                page_prev = api.url_for(self, page=page-1, _external=True)
            page_next = None
            if pagination.has_next:
                page_next = api.url_for(self, page=page+1, _external=True)

        # if not experiments:
        #     return [], 200

        result = experiment_schema.dump(experiments, many=True).data

        return result, 200

    def post(self):
        parsed_args = parser.parse_args()
        exp_type = parsed_args['exp_type']
        name = parsed_args['name']
        date = parsed_args['date']
        experimenter = parsed_args['experimenter']
        species = parsed_args['species']
        tissue = parsed_args['tissue']
        information = parsed_args['information']
        experiment = Experiment(exp_type=exp_type, name=name, date=date, experimenter=experimenter, species=species, tissue=tissue, information=information)
        db.session.add(experiment)
        db.session.commit()
        result = experiment_schema.dump(experiment, many=False).data
        return result, 201

class ExperimentController(Resource):

    # For a given file, return whether it's an allowed type or not
    def is_allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    def get(self, experiment_id):
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, "Experiment {} doesn't exist".format(experiment_id))
        result = experiment_schema.dump(experiment).data
        return result, 200

    def delete(self, experiment_id):
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, "Experiment {} doesn't exist".format(experiment_id))
        db.session.delete(experiment)
        db.session.commit()
        return {}, 204

    def put(self, experiment_id):
        parsed_args = parser.parse_args()
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, "Experiment {} doesn't exist".format(experiment_id))
        experiment.name = parsed_args['name']
        experiment.experimenter = parsed_args['experimenter']
        db.session.add(experiment)
        db.session.commit()
        result = experiment_schema.dump(experiment).data
        return result, 200

class ExperimentFileListController(Resource):

    # For a given file, return whether it's an allowed type or not
    def is_allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    def post(self, experiment_id):
        # get uploaded file
        parsed_args = parser.parse_args()
        newFile = parsed_args['files[]'][0]
        # http://werkzeug.pocoo.org/docs/0.11/datastructures/#werkzeug.datastructures.FileStorage
        mimetype = newFile.mimetype;

        # Make the filename safe, remove unsupported chars
        file_name = werkzeug.secure_filename(newFile.filename)

        # get experiment
        experiment = Experiment.query.get(experiment_id)

        # setup uploads folder
        # see https://web.archive.org/web/20160331205619/http://stackoverflow.com/questions/273192/how-to-check-if-a-directory-exists-and-create-it-if-necessary
        file_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER'), sha1_string(experiment.name))
        try:
            os.makedirs(file_folder)
        except OSError:
            if not os.path.isdir(file_folder):
                abort(404, "Unable to access {}".format(file_folder))

        # define file path
        file_path = os.path.join(file_folder, file_name)

        # handle chunked file upload
        if parsed_args['Content-Range'] and newFile and self.is_allowed_file(newFile.filename):
            # extract byte numbers from Content-Range header string
            content_range = parsed_args['Content-Range']
            range_str = content_range.split(' ')[1]
            start_bytes = int(range_str.split('-')[0])
            end_bytes = int(range_str.split('-')[1].split('/')[0])
            total_bytes = int(range_str.split('/')[1])

            # append chunk to the file on disk, or create new
            with open(file_path, 'a') as f:
                f.seek(start_bytes)
                f.write(newFile.stream.read())

            # check if these are the last bytes
            # if so, create experiment
            if end_bytes >= (total_bytes - 1):
                experimentFile = ExperimentFile(experiment_id=experiment_id, file_name=file_name, file_path=file_path, file_size=total_bytes, file_mimetype=mimetype)
                db.session.add(experimentFile)
                db.session.commit()
                result = experiment_file_schema.dump(experimentFile, many=False).data
                return result, 201
            # otherwise, return range as string
            else:
                return range_str, 201

        # handle small/complete file upload
        # Check if the file is one of the allowed types/extensions
        elif newFile and self.is_allowed_file(newFile.filename):
            newFile.save(file_path)
            file_size = os.stat(file_path).st_size
            experimentFile = ExperimentFile(experiment_id=experiment_id, file_name=file_name, file_path=file_path, file_size=file_size, file_mimetype=mimetype)
            db.session.add(experimentFile)
            db.session.commit()
            result = experiment_file_schema.dump(experimentFile, many=False).data
            return result, 201
        else:
            abort(404, "No file sent")

    def get(self, experiment_id):
        # access querystring arguments to filter files by group
        parser.add_argument('group', location=['args'])
        parsed_args = parser.parse_args()
        filters = {}
        filters['experiment_id'] = experiment_id
        if (parsed_args['group']):
            filters['file_group'] = parsed_args['group']
            # use unpacking here for passing an arbitrary bunch of keyword arguments to filter_by
            # http://stackoverflow.com/a/19506429
            # http://docs.python.org/release/2.7/tutorial/controlflow.html#unpacking-argument-lists
        experiment_files = ExperimentFile.query.filter_by(**filters).all()
        result = experiment_file_schema.dump(experiment_files, many=True).data
        return result, 200


class ExperimentFileController(Resource):

    @api.representation('text/tab-separated-values')
    def get(self, experiment_id, file_id):
        experiment_file = ExperimentFile.query.filter_by(experiment_id=experiment_id, id=file_id).first()
        with open(experiment_file.file_path, 'r') as data_file:
            data = data_file.read()
        resp = make_response(data, 200)
        resp.headers['content-type'] = 'text/tab-separated-values'
        return resp


class ExperimentAnalysisListController(Resource):

    def get(self, experiment_id):
        experiment_analyses = ExperimentAnalysis.query.filter_by(experiment_id=experiment_id).all()
        result = experiment_analysis_schema.dump(experiment_analyses, many=True).data
        return result, 200

    pipeline_args = {
        'pipeline_id': fields.Str(),
        'command': fields.Str(),
        'parameters': fields.Nested({
            'inputs': fields.List(fields.Dict()),
            'outputs': fields.List(fields.Dict())
        })
    }
    # example object
    # {
    #     "pipeline_id": "examplePipeline",
    #     "command": "sh ./examplePipeline.sh $input1 $input2 $output",
    #     "parameters": {
    #     	"inputs": [
    #     		{"input1": "'This is a test'"},
    #           {"input2": "'This is another test'"}
    #     	],
    #     	"outputs": [
    #           {"output": "testOutput.txt"}
    #     	]
    #     }
    # }
    @use_args(pipeline_args)
    def post(self, args, experiment_id):
        from string import Template

        # merge input dictionaries (key-value pairs) into one single dictionary for inputs
        input_params = {key: value for d in args['parameters']['inputs'] for key, value in d.items()}
        # merge output dictionaries into one single dictionary for outputs
        output_params = {key: value for d in args['parameters']['outputs'] for key, value in d.items()}
        # merge both dictionaries, note that for duplicated keys, only the value of the second dict is stored, but parameters should be unique anyway
        pipeline_parameters = dict()
        pipeline_parameters.update(input_params)
        pipeline_parameters.update(output_params)

        # write params into command template
        pipeline_command = args['command']
        pipeline_command = Template(pipeline_command)
        final_pipeline_command = pipeline_command.substitute(pipeline_parameters)

        task = execute_command.delay(final_pipeline_command)
        # experiment_analysis = ExperimentAnalysis(experiment_id=experiment_id, pipeline_id=args['pipeline_id'], inputs=inputs, outputs=outputs)
        # db.session.add(experiment_analysis)
        # db.session.commit()
        # result = experiment_analysis_schema.dump(experiment_analysis).data

        return {}, 202, {'Location': api.url_for(tasks.TaskStatusController, task_id=task.id)}


class ExperimentAnalysisController(Resource):

    def get(self, experiment_id, analysis_id):
        experiment_analysis = ExperimentAnalysis.query.filter_by(experiment_id=experiment_id, id=analysis_id).first()
        result = experiment_analysis_schema.dump(experiment_analysis).data
        return result, 200

    def delete(self, experiment_id, analysis_id):
        experiment_analysis = ExperimentAnalysis.query.filter_by(experiment_id=experiment_id, id=analysis_id).first()
        if not experiment_analysis:
            abort(404, "Analysis {} for experiment {} doesn't exist".format(experiment_id, analysis_id))
        db.session.delete(experiment_analysis)
        db.session.commit()
        return {}, 204
