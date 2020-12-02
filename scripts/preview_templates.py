#!/usr/bin/env python
import argparse
import logging
import sys
from DNACTemplate import DNACTemplate

parser = argparse.ArgumentParser(description='Preview DNAC templates rendering result')
parser.add_argument('--deploy_dir', required=True, help='directory or single file with yaml deployment config')
parser.add_argument('--outfile', help='write preview result to this file')
parser.add_argument('--debug', action='store_true', help='print more debugging output')
parser.add_argument('--config', help='config file to use')
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

dnac = DNACTemplate(config_file=args.config)
result = dnac.preview_templates(args.deploy_dir, preview_file=args.outfile)
sys.exit(0 if result else 1)
