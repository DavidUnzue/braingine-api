#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource

from server.models.plot import PlotSchema
import os, json, glob


plot_schema = PlotSchema()

class PlotListController(Resource):
    def get(self):
        # get json files (plot definition files) from plots folder
        plot_files = glob.glob(os.path.join(current_app.config.get('PLOTS_STORAGE'), '**/*.json'), recursive=True)

        plot_definition_list = list()
        for plot_file in plot_files:
            with open(plot_file) as plot_definition_file:
                plot_definition = json.load(plot_definition_file)
                plot_definition_list.append(plot_definition)

        result = plot_schema.dump(plot_definition_list, many=True).data
        return result, 200


class PlotController(Resource):
    def get(self, plot_uid):

        plot_definition_file_path = os.path.join(current_app.config.get('PLOTS_STORAGE'), plot_uid, '{}.json'.format(plot_uid))

        try:
            with open(plot_definition_file_path) as plot_definition_file:
                plot_definition = json.load(plot_definition_file)
        except OSError:
            abort(404, "Could not find plot file {}.json".format(plot_uid))

        result = plot_schema.dump(plot_definition).data
        return result, 200
