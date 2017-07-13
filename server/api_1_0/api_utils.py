import werkzeug, os, shutil, magic
from flask import current_app
from ..models.experiment import Experiment, ExperimentFile
from ..utils import sha1_string
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


def file_upload(temp_filename, filename, experiment_id):
        # Make the filename safe, remove unsupported chars
        filename = werkzeug.secure_filename(filename)

        # get experiment
        experiment = Experiment.query.get(experiment_id)

        experiment_folder = sha1_string(experiment.name)

        # path to the file in the storage server
        file_path = os.path.join(current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), filename)

        file_path_internal = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), file_path)

        # destination where python should write the file to internally, using the symlink to the mounted storage server
        # write_file_to = os.path.join(current_app.config.get('DATA_ROOT_INTERNAL'), current_app.config.get('EXPERIMENTS_FOLDER'), experiment_folder, current_app.config.get('UPLOADS_FOLDER'), filename)
        # move file from preuploads to corresponding uploads folder
        shutil.move(os.path.join(current_app.config.get('SYMLINK_TO_DATA_STORAGE_PREUPLOADS'), temp_filename), file_path_internal)

        # initialize file handle for magic file type detection
        fh_magic = magic.Magic(magic_file=current_app.config.get('BIOINFO_MAGIC_FILE'), uncompress=True)
        # get bioinformatic file type using magic
        file_format_full = fh_magic.from_file(file_path_internal)
        # get mimetype of file using magic
        mimetype = magic.from_file(file_path_internal, mime=True)
        # get file size
        file_stats = os.stat(file_path_internal)
        file_size = file_stats.st_size

        experimentFile = ExperimentFile(experiment_id=experiment_id, size_in_bytes=file_size, name=filename, path=file_path, folder=experiment_folder, mime_type=mimetype, file_format_full=file_format_full, is_upload=True)
        db.session.add(experimentFile)
        db.session.commit()

        return experimentFile
