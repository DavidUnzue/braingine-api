import os, errno, hashlib, shutil


# def create_dir(directory):
#     """
#     Create an empty directory in the specified path
#     """
#     # see https://web.archive.org/web/20160331205619/http://stackoverflow.com/questions/273192/how-to-check-if-a-directory-exists-and-create-it-if-necessary
#     try:
#         os.makedirs(directory)
#     except OSError:
#         if not os.path.isdir(directory):
#             abort(404, {'message': "Unable to access {}".format(directory)})


def silent_remove(path):
    """
    Remove file from filesystem without raising an error if it does not exist
    """
    # http://stackoverflow.com/questions/12450113/sqlalchemy-flask-after-insert-update-delete
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=False, onerror=onerror)
    else:
        try:
            os.remove(path)
        except OSError as e: # this would be "except OSError, e:" before Python 2.6
            if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
                raise # re-raise exception if a different error occured


# http://stackoverflow.com/a/2656405
def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def sha1_string(string):
    """
    Create SHA1 hash of a given string.
    SHA-1 Hash is 20 bytes long. Hexdigest is twice that long, 40 bytes.
    """
    hash_object = hashlib.sha1(string)
    hex_dig = hash_object.hexdigest()
    return hex_dig
