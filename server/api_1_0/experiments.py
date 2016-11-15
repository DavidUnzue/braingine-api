#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, os, werkzeug, magic, json
from flask import abort, make_response, current_app, request
from flask.ext.restful import Resource, reqparse
from auth import auth
# Import db instance
from server import db
# Import models from models.py file
# IMPORTANT!: this has to be done after the DB gets instantiated and in this case imported too
from server.models.experiment import Experiment, ExperimentSchema, ExperimentFile, ExperimentFileSchema, ExperimentAnalysis, ExperimentAnalysisSchema, ExperimentAnalysisParameter, ExperimentAnalysisParameterSchema
from server.utils import sha1_string, connect_ssh, write_file, write_file_remote
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
parser.add_argument('q', location=['args'])


class ExperimentListController(Resource):
    decorators = [auth.login_required]

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

    @use_args({
        'content-range': fields.Str(load_from='Content-Range', location='headers', missing=None),
        'content-length': fields.Int(load_from='Content-Length', location='headers', missing=0)
    })
    def post(self, args, experiment_id):
        parser.add_argument('files[]', action='append', type=werkzeug.datastructures.FileStorage, location=['files']) # TODO add custom marshmallow field
        # get uploaded file
        parsed_args = parser.parse_args()
        newFile = parsed_args['files[]'][0] # only one file per post request

        # get file type
        # http://werkzeug.pocoo.org/docs/0.11/datastructures/#werkzeug.datastructures.FileStorage
        mimetype = newFile.mimetype;

        # Make the filename safe, remove unsupported chars
        file_name = werkzeug.secure_filename(newFile.filename)

        # get experiment
        experiment = Experiment.query.get(experiment_id)

        # setup uploads folder for experiment files
        file_folder = os.path.join(current_app.config.get('UPLOAD_FOLDER'), sha1_string(experiment.name))

        # define file path
        file_path = os.path.join(file_folder, file_name)

        # upload file
        if newFile:
            # file format is in allowed formats list defined in config
            if self.is_allowed_file(file_name):


                # connect to remote file storage server
                # ssh = connect_ssh(current_app.config.get('COMPUTING_SERVER_IP'), current_app.config.get('COMPUTING_SERVER_USER'), current_app.config.get('COMPUTING_SERVER_PASSWORD'))

                # handle chunked file upload
                if args['content-range']:
                    # get file chunk contents
                    file_buffer = newFile.stream.read(1024)
                    newFile.stream.seek(0)

                    # extract byte numbers from Content-Range header string
                    content_range = args['content-range']
                    range_str = content_range.split(' ')[1]
                    start_bytes = int(range_str.split('-')[0])
                    end_bytes = int(range_str.split('-')[1].split('/')[0])
                    total_bytes = int(range_str.split('/')[1])

                    # append chunk to the file on server, or create new
                    write_file(file_folder, file_name, newFile)

                    # get bioinformatic file type using magic on the first chunk of the file
                    # if start_bytes == 0:
                    #     file_type = fh_magic.from_buffer(file_buffer)

                    # check if these are the last bytes
                    # if so, create experiment
                    if end_bytes >= (total_bytes - 1):
                        # initialize file handle for magic file type detection
                        fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))
                        # get bioinformatic file type using magic on the first chunk of the file
                        file_type = fh_magic.from_buffer(file_buffer)
                        experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=total_bytes, name=file_name, path=file_path, folder=file_folder, mime_type=mimetype, file_type=file_type)
                        db.session.add(experimentFile)
                        db.session.commit()
                        result = experiment_file_schema.dump(experimentFile, many=False).data
                        return result, 201
                    # otherwise, return range as string
                    else:
                        return range_str, 201

                # handle small/non-chunked file upload
                else:

                    file_buffer = newFile.stream.read(1024)
                    newFile.stream.seek(0)

                    # initialize file handle for magic file type detection
                    fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))
                    # get bioinformatic file type using magic on the first chunk of the file
                    file_type = fh_magic.from_buffer(file_buffer)

                    # write_file_remote(ssh, file_folder, file_name, newFile)
                    write_file(file_folder, file_name, newFile)

                    # get file size from request's header content-length
                    file_size = args['content-length']

                    experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=file_size, name=file_name, path=file_path, folder=file_folder, mime_type=mimetype, file_type=file_type)
                    db.session.add(experimentFile)
                    db.session.commit()
                    result = experiment_file_schema.dump(experimentFile, many=False).data
                    return result, 201
            # file format not in allowed files list
            else:
                abort(404, "File format is not allowed")
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

    # Flask Restful representations (i.e. @api.representation('text/tsv')) don't work for content negotiation here, since they apply to the api level, and not to a single resource level. That's why it isn't possible to create resource specific content negotiation.

    def download_file(self, experiment_file, attachment=False):
        """Makes a Flask response with the corresponding content-type encoded body"""
        from flask import send_file
        return send_file(experiment_file.path, mimetype=experiment_file.mime_type, as_attachment=attachment)

    # when request contains header: "Accept: text/tsv"
    # def output_tsv(self, experiment_file, code):
    #     """Makes a Flask response with a tab-separated-values' encoded body"""
    #     from flask import send_file
    #     return send_file(experiment_file.path, mimetype='text/tsv', as_attachment=False)
        # with open(experiment_file.path, 'r') as data_file:
        #     data = data_file.read()
        # resp = make_response(data, code)
        # # resp.headers.extend(headers or {})
        # resp.headers['content-type'] = 'text/tsv'
        # resp.headers['Content-Disposition'] = 'attachment'
        # return resp

    @use_args({
        'accept': fields.Str(load_from='Accept', location='headers'), # default is */* for accepting everything
        'download': fields.Boolean(location='querystring', missing=False) # force download or not
    })
    def get(self, args, experiment_id, file_id):
        experiment_file = ExperimentFile.query.filter_by(experiment_id=experiment_id, id=file_id).first()
        if not experiment_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        # metadata as json requested
        if (args['accept'] == 'application/json'):
            result = experiment_file_schema.dump(experiment_file, many=False).data
            return result, 200
        # otherwise send file contents
        elif (args['accept'] == experiment_file.mime_type or args['accept'] == '*/*'):
            return self.download_file(experiment_file, args['download'])
        # not acceptable content-type requested
        else:
            abort(406, "The resource identified by the request is only capable of generating response entities which have content characteristics not acceptable according to the accept headers sent in the request.")

    def delete(self, experiment_id, file_id):
        experiment_file = ExperimentFile.query.filter_by(experiment_id=experiment_id, id=file_id).first()
        if not experiment_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        db.session.delete(experiment_file)
        db.session.commit()
        return {}, 204

    @use_args(experiment_file_schema)
    def put(self, args, experiment_id, file_id):
        # TODO change file sha value when changing the file's name
        # args = webargs_parser.parse(experiment_file_schema, request)
        # args, errors = experiment_file_schema.load(request.json)
        experiment_file = ExperimentFile.query.filter_by(experiment_id=experiment_id, id=file_id).first()
        if not experiment_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        for k, v in args.items():
            if v is not None:
                setattr(experiment_file, k, v)
        db.session.add(experiment_file)
        db.session.commit()
        result = experiment_file_schema.dump(experiment_file).data
        return result, 200


class ExperimentAnalysisListController(Resource):

    def get(self, experiment_id):
        experiment_analyses = ExperimentAnalysis.query.filter_by(experiment_id=experiment_id).all()
        result = experiment_analysis_schema.dump(experiment_analyses, many=True).data
        return result, 200

    analysis_args = {
        'pipeline_id': fields.Str(),
        'command': fields.Str(),
        'parameters': fields.List(fields.Dict())
    }
    # example object
    # {
    #     "pipeline_id": "examplePipeline",
    #     "parameters": [
    #             {"input1": "'This is a test'"},
    #             {"input2": "'This is another test'"}
    #             {"output": "testOutput.txt"}
    #     ]
    # }
    @use_args(analysis_args)
    def post(self, args, experiment_id):
        from string import Template

        # comment following lines out if parameters contained in inputs and outputs arrays
        # # merge input dictionaries (key-value pairs) into one single dictionary for inputs
        # input_params = {key: value for d in args['parameters']['inputs'] for key, value in d.items()}
        # # merge output dictionaries into one single dictionary for outputs
        # output_params = {key: value for d in args['parameters']['outputs'] for key, value in d.items()}
        # # merge both dictionaries, note that for duplicated keys, only the value of the second dict is stored, but parameters should be unique anyway
        # pipeline_parameters = dict()
        # pipeline_parameters.update(input_params)
        # pipeline_parameters.update(output_params)

        # merge parameter dictionaries (key-value pairs) into one single dictionary, in order to work on Template.substitute
        pipeline_parameters = {key: value for d in args['parameters'] for key, value in d.items()}

        # get pipeline command
        with open('{}/{}.json'.format(current_app.config.get('PIPELINES_FOLDER'), args['pipeline_id'])) as pipeline_definition_file:
            pipeline_definition = json.load(pipeline_definition_file)
            pipeline_command = pipeline_definition['command']

        # write params into command template
        pipeline_command = Template(pipeline_command)
        final_pipeline_command = pipeline_command.substitute(pipeline_parameters)

        # send task to celery and store it in a variable for returning task id in location header
        task = execute_command.delay(final_pipeline_command)

        # add DB entry for analysis
        experiment_analysis = ExperimentAnalysis(experiment_id=experiment_id, pipeline_id=args['pipeline_id'])
        db.session.add(experiment_analysis)
        db.session.commit()

        # add DB entries for parameters for the analysis created before
        for name, value in pipeline_parameters.iteritems():
            analysis_parameters = ExperimentAnalysisParameter(experiment_analysis_id=experiment_analysis.id, parameter_name=name, parameter_value=value)
            db.session.add(analysis_parameters)
            db.session.commit()

        result = experiment_analysis_schema.dump(experiment_analysis).data

        return result, 202, {'Location': api.url_for(tasks.TaskStatusController, task_id=task.id)}


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
