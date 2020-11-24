#!/usr/bin/env python
import os
import sys

import yaml
from jinja2 import Environment

YAML_DIRS = ['deployment/']
TEMPLATE_DIRS = ['dnac-templates/']

errors = []

for d in YAML_DIRS:
    for f in os.listdir(d):
        if f.startswith('.'):
            continue

        filename = os.path.join(d, f)
        print('Examining {}'.format(filename))
        try:
            with open(filename) as fd:
                content = fd.read()

            yaml.safe_load(content)
        except Exception as e:
            msg = 'ERROR: YAML validation failed for {}'.format(filename)
            print(msg + ':\n' + str(e))
            errors.append(msg)

for d in TEMPLATE_DIRS:
    for f in os.listdir(d):
        if f.startswith('.'):
            continue

        filename = os.path.join(d, f)
        print('Examining {}'.format(filename))
        try:
            with open(filename) as fd:
                content = fd.read()

            if '{' in content or '}' in content:
                # check if jinja loads it
                Environment().parse(content)
            else:
                # non-jinja not yet covered
                pass
        except Exception as e:
            msg = 'ERROR: Template validation failed for {}'.format(filename)
            print(msg + ':\n' + str(e))
            errors.append(msg)


if len(errors) > 0:
    rc = 1
else:
    rc = 0

sys.exit(rc)
