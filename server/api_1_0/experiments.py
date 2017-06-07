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
from ..utils import sha1_string, sha256checksum, write_file, write_file_in_chunks, create_folder, update_object
from .api_utils import create_pagination_header, create_projection
# http://stackoverflow.com/a/30399108
from . import api
# allow use of or syntax for sql queries
from sqlalchemy import or_
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields
from webargs.flaskparser import use_args


experiment_schema = ExperimentSchema()
experiment_file_schema = ExperimentFileSchema()

# used for getting files from request
parser = reqparse.RequestParser()


class ExperimentListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'where': fields.Str(location='query', missing=None),
        'projection': fields.Str(location='query', missing=None),
        'merge': fields.Bool(location='query', missing=False),
        'q': fields.Str(location='query', missing=None),
        'page': fields.Int(location='query', missing=1),
        'per_page': fields.Int(location='query', missing=None)
    })
    def get(self, args):
        if args['q']:
            # querystring from url should be decoded here
            # see https://unspecified.wordpress.com/2008/05/24/uri-encoding/
            #search_query = urllib.unquote(parsed_args['q']).decode("utf-8")
            search_query = urllib.parse.unquote(args['q'])
            # search for experiments containing the search query in their "name" or "experimenter" attributes
            # use "ilike" for searching case unsensitive
            experiments_query = Experiment.query.filter(or_(Experiment.name.ilike('%'+ search_query + '%'),\
            Experiment.experimenter.ilike('%'+ search_query + '%'),\
            Experiment.exp_type.ilike('%'+ search_query + '%'),\
            Experiment.species.ilike('%'+ search_query + '%'),\
            Experiment.tissue.ilike('%'+ search_query + '%')))
        elif args['where']:
            filters = json.loads(args['where'])
            experiments_query = Experiment.query.filter_by(**filters)
        else:
            experiments_query = Experiment.query

        if args['projection']:
            projection = json.loads(args['projection'])
            experiments_query = create_projection(experiments_query, projection)
        if args['merge']:
            experiments_query = experiments_query.distinct()

        # create pagination
        page = args['page']
        per_page = args['per_page'] or current_app.config.get('ITEMS_PER_PAGE')
        pagination = experiments_query.paginate(page, per_page, False)
        # pagination headers
        link_header = create_pagination_header(self, pagination, page)

        # reponse body
        experiments = pagination.items
        result = experiment_schema.dump(experiments, many=True).data

        return result, 200, link_header

    @use_args(experiment_schema)
    def post(self, args):
        # setup  folders for project data
        project_folder = os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE'), sha1_string(args['name']))
        uploads_folder = os.path.join(project_folder, current_app.config.get('UPLOADS_FOLDER'))
        analyses_folder = os.path.join(project_folder, current_app.config.get('ANALYSES_FOLDER'))

        try:
            experiment = Experiment(user_id=g.user.id, **args)
            db.session.add(experiment)
            db.session.commit()
        except SQLAlchemyError:
            abort(404, "Error creating experiment \"{}\"".format(args['name']))

        try:
            create_folder(project_folder)
            create_folder(uploads_folder)
            create_folder(analyses_folder)
        except OSError as err:
            try:
                db.session.delete(experiment)
                db.session.commit()
                silent_remove(project_folder)
            finally:
                abort(404, "Error creating experiment's directory structure on storage service: {}".format(err))


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

    @use_args(experiment_schema)
    def put(self, args, experiment_id):
        experiment = Experiment.query.get(experiment_id)
        if not experiment:
            abort(404, "Experiment {} doesn't exist".format(experiment_id))
        update_object(experiment, args)
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
        'is_upload': fields.Bool(location='querystring', missing=None),
        'page': fields.Int(location='querystring', missing=1),
        'where': fields.Str(location='query', missing=None)
    })
    def get(self, args, experiment_id):
        # pagination
        page = args['page']
        # filtering
        filters = {}
        if args['where'] is not None:
            filters = json.loads(args['where'])
        filters['experiment_id'] = experiment_id
        if args['is_upload'] is not None:
            filters['is_upload'] = args['is_upload']

        # use unpacking here for passing an arbitrary bunch of keyword arguments to filter_by
        # http://stackoverflow.com/a/19506429
        # http://docs.python.org/release/2.7/tutorial/controlflow.html#unpacking-argument-lists
        pagination = ExperimentFile.query.filter_by(**filters).paginate(page, current_app.config.get('ITEMS_PER_PAGE'), False)
        experiment_files = pagination.items
        page_prev = None
        if pagination.has_prev:
            page_prev = api.url_for(self, experiment_id=experiment_id, page=page-1, _external=True)
        page_next = None
        if pagination.has_next:
            page_next = api.url_for(self, experiment_id=experiment_id, page=page+1, _external=True)

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
        update_object(experiment_file, args)
        db.session.add(experiment_file)
        db.session.commit()
        result = experiment_file_schema.dump(experiment_file).data
        return result, 200
