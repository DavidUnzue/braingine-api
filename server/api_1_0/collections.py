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
from ..models.collection import Collection, CollectionSchema
from ..models.file import ExperimentFile, ExperimentFileSchema
from ..utils import sha1_string, sha256checksum, write_file, write_file_in_chunks, create_folder, update_object
from .api_utils import create_pagination_header, create_projection
# http://stackoverflow.com/a/30399108
from . import api
# allow use of or syntax for sql queries
from sqlalchemy import or_, text
# webargs for request parsing instead of flask restful's reqparse
from webargs import fields
from webargs.flaskparser import use_args
from sqlalchemy.exc import SQLAlchemyError


collection_schema = CollectionSchema()
collection_file_schema = ExperimentFileSchema()

# used for getting files from request
parser = reqparse.RequestParser()


class CollectionListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'where': fields.Str(location='query', missing=None),
        'projection': fields.Str(location='query', missing=None),
        'merge': fields.Bool(location='query', missing=False),
        'q': fields.Str(location='query', missing=None),
        'page': fields.Int(location='query', missing=1),
        'per_page': fields.Int(location='query', missing=None),
        'sort_by': fields.Str(location='query', missing=None),
        'order': fields.Str(location='query', missing=None)
    })
    def get(self, args):
        if args['q']:
            # querystring from url should be decoded here
            # see https://unspecified.wordpress.com/2008/05/24/uri-encoding/
            #search_query = urllib.unquote(parsed_args['q']).decode("utf-8")
            search_query = urllib.parse.unquote(args['q'])
            # search for collections containing the search query in their "name" or "collectioner" attributes
            # use "ilike" for searching case unsensitive
            collections_query = Collection.query.filter(or_(Collection.name.ilike('%'+ search_query + '%'),\
            Collection.exp_type.ilike('%'+ search_query + '%')))
        elif args['where']:
            filters = json.loads(args['where'])
            collections_query = Collection.query.filter_by(**filters)
        else:
            collections_query = Collection.query

        if args['projection']:
            projection = json.loads(args['projection'])
            collections_query = create_projection(collections_query, projection)
        if args['merge']:
            collections_query = collections_query.distinct()
        if args['sort_by'] and args['order']:
            sort = "{} {}".format(args['sort_by'], args['order'])
            collections_query = collections_query.order_by(sort)

        # create pagination
        page = args['page']
        per_page = args['per_page'] or current_app.config.get('ITEMS_PER_PAGE')
        pagination = collections_query.paginate(page, per_page, False)
        # pagination headers
        link_header = create_pagination_header(self, pagination, page)

        # reponse body
        collections = pagination.items
        result = collection_schema.dump(collections, many=True).data

        return result, 200, link_header

    @use_args(collection_schema)
    def post(self, args):

        collection = Collection(user_id=g.user.id, name=args['name'], description=args['description'])
        if len(args['files']) > 0:
            for fileId in args['files']:
                currentFile = ExperimentFile.query.get(fileId)
                collection.files.append(currentFile)

        try:
            db.session.add(collection)
            db.session.commit()
        except SQLAlchemyError:
            abort(404, "Error creating collection \"{}\"".format(args['name']))

        result = collection_schema.dump(collection, many=False).data
        return result, 201

class CollectionController(Resource):
    decorators = [auth.login_required]

    # For a given file, return whether it's an allowed type or not
    def is_allowed_file(self, filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1] in current_app.config.get('ALLOWED_EXTENSIONS')

    def get(self, collection_id):
        collection = Collection.query.get(collection_id)
        if not collection:
            abort(404, "Collection {} doesn't exist".format(collection_id))
        result = collection_schema.dump(collection).data
        return result, 200

    def delete(self, collection_id):
        collection = Collection.query.get(collection_id)
        if not collection:
            abort(404, "Collection {} doesn't exist".format(collection_id))
        db.session.delete(collection)
        db.session.commit()
        return {}, 204

    @use_args(collection_schema)
    def put(self, args, collection_id):
        collection = Collection.query.get(collection_id)
        if not collection:
            abort(404, "Collection {} doesn't exist".format(collection_id))

        collection_files = args['files']
        del args['files']
        update_object(collection, args)

        if len(collection_files) > 0:
            for fileId in collection_files:
                currentFile = ExperimentFile.query.get(fileId)
                collection.files.append(currentFile)

        try:
            db.session.add(collection)
            db.session.commit()
        except SQLAlchemyError:
            abort(404, "Error updating collection \"{}\"".format(args['name']))

        result = collection_schema.dump(collection).data
        return result, 200

class CollectionFileListController(Resource):
    decorators = [auth.login_required]

    @use_args({
        'fileIds': fields.List(fields.Int(), missing=[]),
    })
    def post(self, args, collection_id):
        if len(args['fileIds']) > 0:
            collection = Collection.query.get(collection_id)
            for fileId in args['fileIds']:
                currentFile = ExperimentFile.query.get(fileId)
                collection.files.append = currentFile
            return 201, collection.files

    @use_args({
        # access querystring arguments to filter files by is_upload
        'page': fields.Int(location='query', missing=1),
        'per_page': fields.Int(location='query', missing=None),
        'projection': fields.Str(location='query', missing=None),
        'merge': fields.Bool(location='query', missing=False),
        'sort_by': fields.Str(location='query', missing=None),
        'order': fields.Str(location='query', missing=None),
        'where': fields.Str(location='query', missing=None)
    })
    def get(self, args, collection_id):
        # pagination
        page = args['page']
        # filtering
        filters = {}
        if args['where']:
            filters.update(json.loads(args['where']))

        collection = Collection.query.get(collection_id)

        collection_files_query = collection.files.filter_by(**filters)

        if args['projection']:
            projection = json.loads(args['projection'])
            collection_files_query = create_projection(collection_files_query, projection)
        if args['merge']:
            collection_files_query = collection_files_query.distinct()
        if args['sort_by'] and args['order']:
            sort = "{} {}".format(args['sort_by'], args['order'])
            collection_files_query = collection_files_query.order_by(text(sort))

        # create pagination
        page = args['page']
        per_page = args['per_page'] or current_app.config.get('ITEMS_PER_PAGE')
        pagination = collection_files_query.paginate(page, per_page, False)
        # pagination headers
        link_header = create_pagination_header(self, pagination, page, collection_id=collection_id)

        # reponse body
        collection_files = pagination.items
        result = collection_file_schema.dump(collection_files, many=True).data
        return result, 200, link_header


class CollectionFileController(Resource):
    decorators = [auth.login_required]

    # Flask Restful representations (i.e. @api.representation('text/tsv')) don't work for content negotiation here, since they apply to the api level, and not to a single resource level. That's why it isn't possible to create resource specific content negotiation.

    def download_file(self, collection_file, attachment=False):
        """Makes a Flask response with the corresponding content-type encoded body"""
        from flask import send_from_directory
        data_path = os.path.abspath(current_app.config.get('BRAINGINE_ROOT'))
        return send_from_directory(data_path, collection_file.path, mimetype=collection_file.mime_type, as_attachment=attachment)


    @use_args({
        'accept': fields.Str(load_from='Accept', location='headers'), # default is */* for accepting everything
        'download': fields.Boolean(location='querystring', missing=False) # force download or not
    })
    def get(self, args, collection_id, file_id):
        collection_file = ExperimentFile.query.filter_by(collection_id=collection_id, id=file_id).first()
        if not collection_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        # metadata as json requested
        if (args['accept'] == 'application/json'):
            result = collection_file_schema.dump(collection_file, many=False).data
            return result, 200
        # otherwise send file contents
        elif (args['accept'] == collection_file.mime_type or args['accept'] == '*/*'):
            return self.download_file(collection_file, args['download'])
        # not acceptable content-type requested
        else:
            abort(406, "The resource identified by the request is only capable of generating response entities which have content characteristics not acceptable according to the accept headers sent in the request.")

    def delete(self, collection_id, file_id):
        collection_file = ExperimentFile.query.filter_by(collection_id=collection_id, id=file_id).first()
        if not collection_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        db.session.delete(collection_file)
        db.session.commit()
        return {}, 204

    @use_args(collection_file_schema)
    def put(self, args, collection_id, file_id):
        # TODO change file sha value when changing the file's name
        # args = webargs_parser.parse(collection_file_schema, request)
        # args, errors = collection_file_schema.load(request.json)
        collection_file = ExperimentFile.query.filter_by(collection_id=collection_id, id=file_id).first()
        if not collection_file:
            abort(404, "Experiment file {} doesn't exist".format(file_id))
        update_object(collection_file, args)
        db.session.add(collection_file)
        db.session.commit()
        result = collection_file_schema.dump(collection_file).data
        return result, 200
