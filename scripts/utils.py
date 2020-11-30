# Copyright (c) 2019 Cisco and/or its affiliates.
# This software is licensed to you under the terms of the Cisco Sample
# Code License, Version 1.0 (the "License"). You may obtain a copy of the
# License at
#                https://developer.cisco.com/docs/licenses
# All use of the material herein must be in accordance with the terms of
# the License. All rights not expressly granted by the License are
# reserved. Unless required by applicable law or agreed to separately in
# writing, software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import json
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


def update_results_json(filename=None, message=None, stats={}):
    '''
    Update results.json file, creating if it does not exist
    '''
    if not filename:
        return

    try:
        with open(filename, 'r') as fd:
            results = json.loads(fd.read())
    except FileNotFoundError:
        results = {}

    results[message] = stats

    with open(filename, 'w') as fd:
        fd.write(json.dumps(results, indent=2) + '\n')
    return results
