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
from ..models.experiment import Experiment, ExperimentSchema, ExperimentFile, ExperimentFileSchema
from ..utils import sha1_string, sha256checksum, write_file, write_file_in_chunks, create_folder
# http://stackoverflow.com/a/30399108
from . import api
# allow use of or syntax for sql queries
from sqlalchemy import or_
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields
from webargs.flaskparser import use_args


experiment_schema = ExperimentSchema()
experiment_file_schema = ExperimentFileSchema()


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
            search_query = urllib.parse.unquote(parsed_args['q'])
            # search for experiments containing the search query in their "name" or "experimenter" attributes
            # use "ilike" for searching case unsensitive
            experiments = Experiment.query.filter(or_(Experiment.name.ilike('%'+ search_query + '%'), Experiment.experimenter.ilike('%'+ search_query + '%'), Experiment.exp_type.ilike('%'+ search_query + '%'), Experiment.species.ilike('%'+ search_query + '%'), Experiment.tissue.ilike('%'+ search_query + '%'))).all()
        else:
            pagination = Experiment.query.paginate(page, 5, False)
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

        # setup  folders for project data
        project_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), sha1_string(name))
        create_folder(project_folder)

        uploads_folder = os.path.join(project_folder, current_app.config.get('UPLOADS_FOLDER'))
        create_folder(uploads_folder)

        analyses_folder = os.path.join(project_folder, current_app.config.get('ANALYSES_FOLDER'))
        create_folder(analyses_folder)

        experiment = Experiment(user_id=g.user.id, exp_type=exp_type, name=name, date=date, experimenter=experimenter, species=species, tissue=tissue, information=information)
        db.session.add(experiment)
        db.session.commit()
        result = experiment_schema.dump(experiment, many=False).data
        return result, 201

class ExperimentController(Resource):
    decorators = [auth.login_required]

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
    decorators = [auth.login_required]

    # For a given file, return whether it's an allowed type or not
    def is_allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    @use_args({
        'content-range': fields.Str(load_from='Content-Range', location='headers', missing=None),
        'content-length': fields.Int(load_from='Content-Length', location='headers', missing=0),
        'is_upload': fields.Bool(missing=False),
        'filename_in_storage': fields.Str(missing=None)
    })
    def post(self, args, experiment_id):
        parser.add_argument('files[]', action='append', type=werkzeug.datastructures.FileStorage, location=['files']) # TODO add custom marshmallow field

        # get uploaded file
        parsed_args = parser.parse_args()
        # get filename if alternative upload
        filename_in_storage = args['filename_in_storage']

        try:
            newFile = parsed_args['files[]'][0] # only one file per post request
        except TypeError:
            newFile = None

        # Make the filename safe, remove unsupported chars
        try:
            file_name = werkzeug.secure_filename(newFile.filename)
        except AttributeError:
            file_name = werkzeug.secure_filename(filename_in_storage)

        # get experiment
        experiment = Experiment.query.get(experiment_id)

        experiment_folder = sha1_string(experiment.name)

        # destination where python should write the file to internally, using the symlink to the mounted storage server
        write_file_to = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'))

        # path to the file in the storage server
        file_path = os.path.join(current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), file_name)

        file_path_internal = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), file_path)

        # upload file
        if newFile:
            # file format is in allowed formats list defined in config
            if self.is_allowed_file(file_name):

                # get file type
                # http://werkzeug.pocoo.org/docs/0.11/datastructures/#werkzeug.datastructures.FileStorage
                mimetype = newFile.mimetype;

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
                    write_file(write_file_to, file_name, newFile)

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
                        experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=total_bytes, name=file_name, path=file_path, folder=experiment_folder, mime_type=mimetype, file_type=file_type, is_upload=args['is_upload'])
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

                    write_file(write_file_to, file_name, newFile)

                    # get file size from request's header content-length
                    file_size = args['content-length']

                    experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=file_size, name=file_name, path=file_path, folder=experiment_folder, mime_type=mimetype, file_type=file_type, is_upload=args['is_upload'])
                    db.session.add(experimentFile)
                    db.session.commit()
                    result = experiment_file_schema.dump(experimentFile, many=False).data
                    return result, 201
            # file format not in allowed files list
            else:
                abort(404, "File format is not allowed")
        else:
            # check if filename sent as selection from storage server
            if (filename_in_storage):
                import shutil
                # move file from preuploads to corresponding uploads folder
                shutil.move(os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS'), filename_in_storage), write_file_to)

                # initialize file handle for magic file type detection
                fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'))
                # get bioinformatic file type using magic
                file_type = fh_magic.from_file(file_path_internal)
                # get mimetype of file using magic
                mimetype = magic.from_file(file_path_internal, mime=True)
                # get file size
                file_stats = os.stat(file_path_internal)
                file_size = file_stats.st_size

                experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=file_size, name=file_name, path=file_path, folder=experiment_folder, mime_type=mimetype, file_type=file_type, is_upload=args['is_upload'])
                db.session.add(experimentFile)
                db.session.commit()
                result = experiment_file_schema.dump(experimentFile, many=False).data
                return result, 201

            else:
                abort(404, "No file sent")

    @use_args({
        # access querystring arguments to filter files by is_upload
        'is_upload': fields.Bool(location='querystring', missing=None)
    })
    def get(self, args, experiment_id):
        filters = {}
        filters['experiment_id'] = experiment_id
        if args['is_upload'] is not None:
            filters['is_upload'] = args['is_upload']
        # use unpacking here for passing an arbitrary bunch of keyword arguments to filter_by
        # http://stackoverflow.com/a/19506429
        # http://docs.python.org/release/2.7/tutorial/controlflow.html#unpacking-argument-lists
        experiment_files = ExperimentFile.query.filter_by(**filters).all()
        result = experiment_file_schema.dump(experiment_files, many=True).data
        return result, 200


class ExperimentFileController(Resource):
    decorators = [auth.login_required]

    # Flask Restful representations (i.e. @api.representation('text/tsv')) don't work for content negotiation here, since they apply to the api level, and not to a single resource level. That's why it isn't possible to create resource specific content negotiation.

    def download_file(self, experiment_file, attachment=False):
        """Makes a Flask response with the corresponding content-type encoded body"""
        from flask import send_from_directory
        data_path = os.path.abspath(current_app.config.get('DATA_ROOT_INTERNAL'))
        return send_from_directory(data_path, experiment_file.path, mimetype=experiment_file.mime_type, as_attachment=attachment)


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
        for k, v in list(args.items()):
            if v is not None:
                setattr(experiment_file, k, v)
        db.session.add(experiment_file)
        db.session.commit()
        result = experiment_file_schema.dump(experiment_file).data
        return result, 200
