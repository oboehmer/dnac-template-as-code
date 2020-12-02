#!/usr/bin/env python
#
# Use DNAC to deploy templates on devices
#
import argparse
import logging
import sys
from DNACTemplate import DNACTemplate

parser = argparse.ArgumentParser(description='Deploy DNAC templates')
parser.add_argument('--deploy_dir', required=True, help='directory or single file with yaml deployment config')
parser.add_argument('--debug', action='store_true', help='print more debugging output')
parser.add_argument('--config', help='config file to use')
parser.add_argument('--results', help='save results in json in this file (default: no file is created)')
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

dnac = DNACTemplate(config_file=args.config)
result = dnac.deploy_templates(args.deploy_dir, result_json=args.results)
sys.exit(0 if result else 1)
