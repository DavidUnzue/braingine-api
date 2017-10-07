import os, magic
from flask import current_app
from ..models.file import ExperimentFile
from .. import db
from . import api


def create_pagination_header(self, paginated_resource, page, **args):
    """
    Creates a Link item in the HTTP response header with information to sibling pages

    :param flask.ext.sqlalchemy.Pagination paginated_resource: a Flask-SQLALchemy pagination object of a resource
    :param int page: the current page
    """
    link_header = []
    # first page
    page_first_url = api.url_for(self, page=1, **args, _external=True)
    page_first = "<{}>; rel=\"first\"".format(page_first_url)
    link_header.append(page_first)
    # last page
    page_last_url = api.url_for(self, page=paginated_resource.pages, **args, _external=True)
    page_last = "<{}>; rel=\"last\"".format(page_last_url)
    link_header.append(page_last)
    # previous page
    page_prev = None
    if paginated_resource.has_prev:
        page_prev_url = api.url_for(self, page=page-1, **args, _external=True)
        page_prev = "<{}>; rel=\"prev\"".format(page_prev_url)
        link_header.append(page_prev)
    # next page
    page_next = None
    if paginated_resource.has_next:
        page_next_url = api.url_for(self, page=page+1, **args, _external=True)
        page_next = "<{}>; rel=\"next\"".format(page_next_url)
        link_header.append(page_next)

    return {'Link': ",".join(link_header)}


def create_projection(resource_query, projection_args):
    """
    Creates a projection out of a query. Projections are conditional queries where the client dictates which fields should be returned by the API.

    :param sqlalchemy.orm.query.Query resource_query: a SQLALchemy query object of a resource
    :param dict projection_args: fields wich should be included or excluded in the projection
    """
    # get the resource's model being queried
    resource_model = resource_query.column_descriptions[0]['entity']
    included_fields = []
    excluded_fields = []
    for field, include in projection_args.items():
        if include == 1:
            included_fields.append(field)
        elif include == 0:
            excluded_fields.append(field)
    if len(excluded_fields) > 0:
        resource_query = resource_query.with_entities(*[c for c in resource_model.__table__.c if c.name not in excluded_fields])
    elif len(included_fields) > 0:
        resource_query = resource_query.with_entities(*[c for c in resource_model.__table__.c if c.name in included_fields])
    return resource_query


def store_file_upload(filename, user):
    file_path = os.path.join(current_app.config.get('BRAINGINE_ROOT'), current_app.config.get('DATA_FOLDER'), user.username, current_app.config.get('UPLOADS_FOLDER'), filename)
    # initialize file handle for magic file type detection
    fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)
    # get bioinformatic file type using magic
    file_format_full = fh_magic.from_file(file_path)
    # get mimetype of file using magic
    mimetype = magic.from_file(file_path, mime=True)
    # get file size
    file_stats = os.stat(file_path)
    file_size = file_stats.st_size

    experimentFile = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path, mime_type=mimetype, file_format_full=file_format_full, is_upload=True)
    db.session.add(experimentFile)
    db.session.commit()

    return experimentFile


def store_illumina_file(filename, folder_uid, user):
    file_path = os.path.join(current_app.config.get('ILLUMINA_ROOT'), folder_uid, current_app.config.get('ILLUMINA_FASTQ_FOLDER'), filename)
    # path in braingine folder
    file_path_internal = os.path.join(current_app.config.get('BRAINGINE_ROOT'), current_app.config.get('DATA_FOLDER'), user.username, current_app.config.get('UPLOADS_FOLDER'), filename)

    # create symlink from braingine folder to storage server
    try:
        os.symlink(file_path, file_path_internal)
    except OSError:
        file_path_internal = file_path

    # initialize file handle for magic file type detection
    fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)
    # get bioinformatic file type using magic
    file_format_full = fh_magic.from_file(file_path)
    # get mimetype of file using magic
    mimetype = magic.from_file(file_path, mime=True)
    # get file size
    file_stats = os.stat(file_path)
    file_size = file_stats.st_size


    experimentFile = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path_internal, mime_type=mimetype, file_format_full=file_format_full, is_upload=True)
    db.session.add(experimentFile)
    db.session.commit()

    return experimentFile


def store_storage_file(file_path, user):
    filename = os.path.basename(file_path)
    # path in braingine folder
    file_path_internal = os.path.join(current_app.config.get('BRAINGINE_ROOT'), current_app.config.get('DATA_FOLDER'), user.username, current_app.config.get('UPLOADS_FOLDER'), filename)

    # create symlink from braingine folder to storage server
    try:
        os.symlink(file_path, file_path_internal)
    except OSError:
        file_path_internal = file_path

    # initialize file handle for magic file type detection
    fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)
    # get bioinformatic file type using magic
    file_format_full = fh_magic.from_file(file_path)
    # get mimetype of file using magic
    mimetype = magic.from_file(file_path, mime=True)
    # get file size
    file_stats = os.stat(file_path)
    file_size = file_stats.st_size


    experimentFile = ExperimentFile(user_id=user.id, size_in_bytes=file_size, name=filename, path=file_path_internal, mime_type=mimetype, file_format_full=file_format_full, is_upload=True)
    db.session.add(experimentFile)
    db.session.commit()

    return experimentFile
