import os
import re

import yaml
from attrdict import AttrDict


def replace_env_vars(val):
    '''
    recursively replace references to environment variables in dict or list
    strings (i.e. '%ENV{foobar}') by their respective value
    '''
    def _replace_env(val):
        m = re.match(r'%ENV{([^)]+)}$', val)
        if m:
            return os.environ.get(m.group(1), '')
        else:
            return val

    if isinstance(val, str):
        val = _replace_env(val)
    elif isinstance(val, list):
        for i, v in enumerate(val):
            val[i] = replace_env_vars(v)
    elif isinstance(val, dict):
        for k, v in val.items():
            val[k] = replace_env_vars(v)
    return val


def read_config(config_file):
    with open(config_file) as fd:
        attrs = yaml.safe_load(fd.read())

    # expand env vars
    return AttrDict(replace_env_vars(attrs))


if __name__ == '__main__':
    print(read_config(os.path.join(os.path.dirname(__file__), 'config.yaml')))
