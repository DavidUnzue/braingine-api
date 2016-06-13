# -*- coding: utf-8 -*-
from flask import render_template, Blueprint

index_view = Blueprint('index', __name__)

# match any url and serve always the index template. This is needed for HTML5 pushState
@index_view.route('/', defaults={'path': ''})
@index_view.route('/<path:path>')
def index(path):
    return render_template('index.html')
