#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource

from server.models.plot import PlotSchema
import json


plot_schema = PlotSchema()

class PlotListController(Resource):
    def get(self):
        from os import listdir
        from os.path import isfile, join
        # get json files (plot definition files) from plots folder
        plot_files = [f for f in listdir(current_app.config.get('PLOTS_FOLDER')) if isfile(join(current_app.config.get('PLOTS_FOLDER'), f)) and f.endswith(".json")]

        plot_definition_list = list()
        for plot_file in plot_files:
            with open('{}/{}'.format(current_app.config.get('PLOTS_FOLDER'), plot_file)) as plot_definition_file:
                plot_definition = json.load(plot_definition_file)
                plot_definition_list.append(plot_definition)

        return plot_definition_list, 200


class PlotController(Resource):
    def get(self, plot_filename):

        try:
            with open('{}/{}.json'.format(current_app.config.get('PLOTS_FOLDER'), plot_filename)) as plot_definition_file:
                plot_definition = json.load(plot_definition_file)
        except OSError:
            abort(404, "Could not find plot file {}.json".format(plot_filename))
        return plot_definition, 200
