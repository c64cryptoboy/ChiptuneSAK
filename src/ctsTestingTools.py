import hashlib
import re

def md5_hash_no_spaces(input):
    input = re.sub('\\s', '', input)
    md5 = hashlib.md5(input.encode('ascii', 'ignore'))
    return md5.hexdigest()

def md5_hash_no_spaces_file(filename):
    with open(filename, 'r') as f:
        input = f.read()
    return md5_hash_no_spaces(input)
