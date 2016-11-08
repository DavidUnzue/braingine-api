from flask import jsonify, make_response
from flask.ext.httpauth import HTTPBasicAuth
auth = HTTPBasicAuth()

users = {
    "david": "test"
}

@auth.get_password
def get_pw(username):
    if username in users:
        return users.get(username)
    return None

@auth.error_handler
def unauthorized():
    resp = make_response(jsonify({'error': 'Unauthorized access'}), 401)
    # avoid browser auth. popup for 401 status
    resp.headers['WWW-Authenticate'] = 'NoPopupBasic realm="Authentication Required"'
    return resp

# TODO implement verification with db stored, hashed passwords
# @auth.verify_password
# def verify_password(username, password):
#     user = User.query.filter_by(username = username).first()
#     if not user or not user.verify_password(password):
#         return False
#     g.user = user
#     return True
