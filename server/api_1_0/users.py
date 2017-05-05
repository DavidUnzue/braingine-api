#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import abort, current_app
from flask.ext.restful import Resource
from .auth import auth
from server.models.user import User, UserSchema


user_schema = UserSchema()

class UserListController(Resource):
    decorators = [auth.login_required]

    def get(self):
        users = User.query.all()
        result = user_schema.dump(users, many=True).data
        return result, 200


class UserController(Resource):
    decorators = [auth.login_required]

    def get(self, user_id):
        user = User.query.get(user_id)
        result = user_schema.dump(user).data
        return result, 200
