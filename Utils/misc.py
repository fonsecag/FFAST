import hashlib
import re


def md5FromArraysAndStrings(*args):
    fp = hashlib.md5()

    for arg in args:
        if isinstance(arg, str):
            d = arg.encode("utf8")
        else:
            d = arg.ravel()

        fp.update(hashlib.md5(d).digest())

    return fp.hexdigest()


def removeExtension(path):
    if "." not in path:
        return path

    if path.startswith("."):
        return path.replace(".", "")

    match = re.match("^(.*)\.(.*)$", path)
    if match is None:
        return path.replace(".", "")
    else:
        return match.group(1).replace(".", "")
