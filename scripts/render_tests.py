#!/usr/bin/env python
import argparse
import logging
import sys
from DNACTemplate import DNACTemplate

parser = argparse.ArgumentParser(description='Deploy DNAC templates')
parser.add_argument('--deploy_dir', required=True, help='directory or single file with yaml deployment config')
parser.add_argument('--out_dir', required=True, help='write tests to this directory')
parser.add_argument('--debug', action='store_true', help='print more debugging output')
parser.add_argument('--config', help='config file to use')
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

dnac = DNACTemplate(config_file=args.config, connect=False)
result = dnac.render_tests(args.deploy_dir, args.out_dir)
sys.exit(0 if result else 1)
