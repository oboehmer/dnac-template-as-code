#!/usr/bin/env python
#
# Validate template files and YAML deployment files
#
import os
import sys

from jinja2 import Environment
from DNACTemplate import DNACTemplate

DEPLOYMENT_DIRS = ['deployment/', 'deployment-preprod/']
TEMPLATE_DIRS = ['dnac-templates/']

errors = []

dnac = DNACTemplate(connect=False)

for d in DEPLOYMENT_DIRS:
    for f in os.listdir(d):
        if f.startswith('.') or not (f.endswith('.yaml') or f.endswith('.yml')):
            continue

        filename = os.path.join(d, f)
        print('Examining {}'.format(filename))
        try:
            dnac.parse_deployment_file(filename)
        except Exception as e:
            msg = 'ERROR: YAML deployment validation failed for {}'.format(filename)
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
