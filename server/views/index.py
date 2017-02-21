# -*- coding: utf-8 -*-
from flask import send_file, Blueprint

index_view = Blueprint('index', __name__)

# match any url and serve always the index template. This is needed for HTML5 pushState
@index_view.route('/', defaults={'path': ''})
@index_view.route('/<path:path>')
def index(path):
    return send_file('./static/index.html')
