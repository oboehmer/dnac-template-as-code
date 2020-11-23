#!/usr/bin/env python
import argparse
import logging
import sys
from DNACTemplate import DNACTemplate

parser = argparse.ArgumentParser(description='Provision DNAC templates')
parser.add_argument('--template_dir', required=True, help='template directory')
parser.add_argument('--debug', action='store_true', help='print more debugging output')
parser.add_argument('--config', help='config file to use')
parser.add_argument('--project', help='DNAC template project (default: taken from config)')
parser.add_argument('--results', help='save results in json in this file (default: no file is created)')
parser.add_argument('--nopurge', action="store_true", help='Don\'t delete templates found on DNAC which are not in the repo')
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

service = DNACTemplate(config_file=args.config, project=args.project)
result = service.provision_templates(args.template_dir, purge=not args.nopurge, result_json=args.results)
sys.exit(0 if result else 1)
