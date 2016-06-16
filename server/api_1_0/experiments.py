#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, os, werkzeug
from flask import abort, send_from_directory, make_response, current_app
from flask.ext.restful import Resource, reqparse, fields, marshal_with, marshal
# Import db instance
from server import db
# Import models from models.py file
# IMPORTANT!: this has to be done after the DB gets instantiated and in this case imported too
from server.models import Experiment, ExperimentFile
from server.utils import sha1_string
# ssh package
from pexpect import pxssh
# http://stackoverflow.com/a/30399108
from . import api
# allow use of or syntax for sql queries
from sqlalchemy import or_


parser = reqparse.RequestParser()
# The default argument type is a unicode string. This will be str in python3 and unicode in python2.
parser.add_argument('exp_type', location=['form', 'json'])
parser.add_argument('name', location=['form', 'json'])
parser.add_argument('date', location=['form', 'json'])
parser.add_argument('experimenter', location=['form', 'json'])
parser.add_argument('species', location=['form', 'json'])
parser.add_argument('tissue', location=['form', 'json'])
parser.add_argument('files[]', action='append', type=werkzeug.datastructures.FileStorage, location=['files'])
parser.add_argument('Content-Range', location=['headers'])
parser.add_argument('q', location=['args'])

experiment_fields = {
    'id': fields.Integer,
    'date_created': fields.DateTime,
    'date_modified': fields.DateTime,
    'exp_type': fields.String,
    'name': fields.String,
    'date': fields.String,
    'experimenter': fields.String,
    'species': fields.String,
    'tissue': fields.String
    #'uri': fields.Url('experiment')
}

experiment_file_fields = {
    'id': fields.Integer,
    'date_created': fields.DateTime,
    'date_modified': fields.DateTime,
    'experiment_id': fields.Integer,
    'file_name': fields.String,
    'file_path': fields.String,
    'file_size': fields.Integer,
    'file_group': fields.String,
}

class ExperimentListController(Resource):
    # do marshalling with marshal function instead of marshal_with decorator in order to be able to return empty object,
    # otherwise the decorator is marshalling also the empty object and applying the experiment_fields with NULL values
    def get(self, page=1):
        parsed_args = parser.parse_args()
        if parsed_args['q']:
            # querystring from url should be decoded here
            # see https://unspecified.wordpress.com/2008/05/24/uri-encoding/
            #search_query = urllib.unquote(parsed_args['q']).decode("utf-8")
            search_query = urllib.unquote(parsed_args['q'])
            # search for experiments containing the search query in their "name" or "experimenter" attributes
            # use "ilike" for searching case unsensitive
            experiments = Experiment.query.filter(or_(Experiment.name.ilike('%'+ search_query + '%'), Experiment.experimenter.ilike('%'+ search_query + '%'), Experiment.exp_type.ilike('%'+ search_query + '%'), Experiment.species.ilike('%'+ search_query + '%'), Experiment.tissue.ilike('%'+ search_query + '%'))).all()
        else:
            #experiments = Experiment.query.paginate(page, 10).items
            experiments = Experiment.query.all()

        if not experiments:
            return [], 200

        return marshal(experiments, experiment_fields), 200

    @marshal_with(experiment_fields)
    def post(self):
        parsed_args = parser.parse_args()
        exp_type = parsed_args['exp_type']
        name = parsed_args['name']
        date = parsed_args['date']
        experimenter = parsed_args['experimenter']
        species = parsed_args['species']
        tissue = parsed_args['tissue']
        experiment = Experiment(exp_type=exp_type, name=name, date=date, experimenter=experimenter, species=species, tissue=tissue)
        db.session.add(experiment)
        db.session.commit()
        return experiment, 201


class ExperimentController(Resource):

    # For a given file, return whether it's an allowed type or not
    def allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    @marshal_with(experiment_fields)
    def get(self, experiment_id):
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, {'message': "Experiment {} doesn't exist".format(experiment_id)})
        return experiment

    def delete(self, experiment_id):
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, {'message': "Experiment {} doesn't exist".format(experiment_id)})
        db.session.delete(experiment)
        db.session.commit()
        return {}, 204

    @marshal_with(experiment_fields)
    def put(self, experiment_id):
        parsed_args = parser.parse_args()
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, {'message': "Experiment {} doesn't exist".format(experiment_id)})
        experiment.name = parsed_args['name']
        experiment.experimenter = parsed_args['experimenter']
        db.session.add(experiment)
        db.session.commit()
        return experiment, 200

class ExperimentFileListController(Resource):

    # For a given file, return whether it's an allowed type or not
    def allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    def post(self, experiment_id):
        # get uploaded file
        parsed_args = parser.parse_args()
        newFile = parsed_args['files[]'][0]

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
                abort(404, {'message': "Unable to access {}".format(file_folder)})

        # define file path
        file_path = os.path.join(file_folder, file_name)

        # handle chunked file upload
        if parsed_args['Content-Range'] and newFile and self.allowed_file(newFile.filename):
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
                experimentFile = ExperimentFile(experiment_id=experiment_id, file_name=file_name, file_path=file_path, file_size=total_bytes)
                db.session.add(experimentFile)
                db.session.commit()
                return marshal(experimentFile, experiment_file_fields), 201
            # otherwise, return range as string
            else:
                return range_str, 201

        # handle small/complete file upload
        # Check if the file is one of the allowed types/extensions
        elif newFile and self.allowed_file(newFile.filename):
            newFile.save(file_path)
            file_size = os.stat(file_path).st_size
            experimentFile = ExperimentFile(experiment_id=experiment_id, file_name=file_name, file_path=file_path, file_size=file_size)
            db.session.add(experimentFile)
            db.session.commit()
            return marshal(experimentFile, experiment_file_fields), 201
        else:
            abort(404, {'message': "No file sent"})

    @marshal_with(experiment_file_fields)
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
        if not experiment_files:
            return [], 200
        return experiment_files


class ExperimentFileController(Resource):

    @api.representation('text/tab-separated-values')
    def get(self, experiment_id, file_id):
        experiment_file = ExperimentFile.query.filter_by(experiment_id=experiment_id, id=file_id).first()
        with open(experiment_file.file_path, 'r') as data_file:
            data = data_file.read()
        resp = make_response(data, 200)
        resp.headers['content-type'] = 'text/tab-separated-values'
        return resp


class ExperimentAnalysisController(Resource):

    def connect_ssh(self):
        s = pxssh.pxssh()
        s.login(current_app.config.get('SSH_SERVER'), current_app.config.get('SSH_USER'), current_app.config.get('SSH_PASSWORD'))
        return s

    def post(self, experiment_id):
        parser.add_argument('cmd', location=['form', 'json'])
        parsed_args = parser.parse_args()
        # run cmd in remote server
        cmd = parsed_args['cmd']
        ssh = self.connect_ssh()
        ssh.sendline(cmd)
        ssh.prompt()
        res = ssh.before
        return res, 201
