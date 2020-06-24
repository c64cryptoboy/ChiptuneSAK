import hashlib
import re
import os
import sys


def md5_hash_no_spaces(input):
    input = re.sub('\\s', '', input)
    md5 = hashlib.md5(input.encode('ascii', 'ignore'))
    return md5.hexdigest()


def md5_hash_no_spaces_file(filename):
    with open(filename, 'r') as f:
        input = f.read()
    return md5_hash_no_spaces(input)


def env_to_stdout():
    print("\nDEBUG environment:")
    print("current working dir:\n%s" % os.getcwd())
    try:
        user_paths = os.environ['PYTHONPATH'].split(os.pathsep)
    except KeyError:
        user_paths = []
    print("python path:\n%s" % user_paths)
    print("os path:\n%s\n" % sys.path)
