import json


def dump_obj(obj):
    def conv(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        return v

    return json.dumps({k: conv(v) for k, v in obj.items()})
