from . import api

def create_pagination_header(self, paginated_resource, page):
    """
    Creates a Link item in the HTTP response header with information to sibling pages

    :param flask.ext.sqlalchemy.Pagination paginated_resource: a Flask-SQLALchemy pagination object of a resource
    :param int page: the current page
    """
    link_header = []
    # first page
    page_first_url = api.url_for(self, page=1, _external=True)
    page_first = "<{}>; rel=\"first\"".format(page_first_url)
    link_header.append(page_first)
    # last page
    page_last_url = api.url_for(self, page=paginated_resource.pages, _external=True)
    page_last = "<{}>; rel=\"first\"".format(page_last_url)
    link_header.append(page_last)
    # previous page
    page_prev = None
    if paginated_resource.has_prev:
        page_prev_url = api.url_for(self, page=page-1, _external=True)
        page_prev = "<{}>; rel=\"prev\"".format(page_prev_url)
        link_header.append(page_prev)
    # next page
    page_next = None
    if paginated_resource.has_next:
        page_next_url = api.url_for(self, page=page+1, _external=True)
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
