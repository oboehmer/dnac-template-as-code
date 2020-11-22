#!/usr/bin/env python
import argparse
from datetime import datetime
import json
import logging
import os
import re
import sys
import time

from dnacentersdk import api
import urllib3
from attrdict import AttrDict
import yaml

urllib3.disable_warnings()
logger = logging.getLogger(os.path.basename(__file__))


class DNACTemplate(object):

    def __init__(self, config_file=None):

        self._read_config(config_file)
        self.template_dir = os.path.join(os.path.dirname(__file__), '../dnac-templates')
        # login to DNAC
        self.dnac = api.DNACenterAPI(**self.config.dnac)
        # get project id, create if not there
        self.template_project_id = self.get_project_id(self.config.template_project)

    def _read_config(self, config_file):
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_file) as fd:
            attrs = yaml.safe_load(fd.read())

        for k, v in attrs['dnac'].items():
            if isinstance(v, str):
                m = re.match(r'%ENV\(([^)]+)\)$', v)
                if m:
                    attrs['dnac'][k] = os.environ.get(m.group(1))
        self.config = AttrDict(attrs)

    def get_project_id(self, project):
        '''
        Retrieve the project ID as we need it in various places. If
        Project doesn't exist, create it
        '''
        for p in self.dnac.configuration_templates.get_projects():
            if p.name == project:
                return p.id

        task = self.dnac.configuration_templates.create_project(name=project)
        project_id = self.wait_and_check_status(task)
        if not project_id:
            raise Exception('Creation of project "{}" failed'.format(project))
        return project_id

    def retrieve_provisioned_templates(self):
        '''
        retrieve a list of templates currently provisioned.
        Returns a dict of template detail dicts, indexed by name
        '''
        logger.debug('Retrieving existing templates')
        result = {}
        for t in self.dnac.configuration_templates.gets_the_templates_available(
                project_id=self.template_project_id):
            # store both template and template details, joining both in the same dict
            result[t.name] = t
            result[t.name].update(self.dnac.configuration_templates.get_template_details(t.templateId))
            logger.debug('Retrieved template {}, full info: {}'.format(t.templateId, result[t.name]))
        return result

    def get_template_params(self, content):
        '''
        extracts referenced jinja2 variables and returns params list.
        TODO: This is not robust, we assume all variables found are strings
        '''
        from jinja2 import Environment, PackageLoader, meta
        env = Environment(loader=PackageLoader('gummi', 'templates'))
        parsed_content = env.parse(content)
        variables = meta.find_undeclared_variables(parsed_content)
        params = []
        order = 1
        for v in variables:
            params.append({
                'parameterName': v,
                'dataType': 'STRING',
                'required': True,
                'order': order,
                'customOrder': 0})
            order += 1
            # d ={'parameterName': 'password', 'dataType': 'STRING', 'defaultValue': None,
            # 'description': None, 'required': True, 'notParam': False, 'paramArray': False,
            # 'displayName': None, 'instructionText': None, 'group': None, 'order': 2,
            # 'customOrder': 0, 'selection': None, 'range': [], 'key': None, 'provider':
            # None, 'binding': '', 'id': '869b0b95-8831-4e9e-9480-5268755bb270'

        return params

    def wait_and_check_status(self, response, max_attempts=2, sleeptime=2):
        attempt = 0
        result = None
        while attempt < max_attempts:
            time.sleep(sleeptime)
            status = self.dnac.task.get_task_by_id(response['response']['taskId'])
            if status.response.isError is False:
                result = status.response.data
                break
            attempt += 1
            logger.debug('waiting, response was {}'.format(status.response))

        if not result:
            raise Exception()
        return result

    def provision_templates(self, purge=True, result_json=None):
        '''
        Push all templates found in our git repo to DNAC
        TODL Templates which have previously provisioned but which have been removed
        on git are also removed from DNAC
        '''
        errors = 0
        results = {
            'message': 'DNAC template provisioning run from {} UTC'.format(datetime.utcnow()),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'deleted': 0,
        }

        # first remember which customers are currently provisioned so we can
        # handle deletion of the whole customer file
        provisioned_templates = self.retrieve_provisioned_templates()
        if len(provisioned_templates) > 0:
            logger.debug('provisioned templates: {}'.format(', '.join(provisioned_templates.keys())))
            for t in provisioned_templates.values():
                logger.debug(t)
        else:
            logger.debug('no templates provisioned.')

        pushed_templates = []

        # process all the templates found in the repo
        for template_file in os.listdir(self.template_dir):
            logger.debug('processing file "{}"'.format(template_file))

            with open(os.path.join(self.template_dir, template_file), 'r') as fd:
                template_content = fd.read()

            template_name = template_file

            current_template = provisioned_templates.get(template_name)
            if not current_template:
                # new template
                params = {
                    'project_id': self.template_project_id,
                    'name': template_name,
                    'description': '',
                    'containingTemplates': [],
                    'language': 'JINJA',
                    'composite': False,
                    'deviceTypes': [{'productFamily': 'Switches and Hubs'}],
                    'softwareType': "IOS-XE",
                    'softwareVersion': None,
                    'tags': [],
                    'templateParams': self.get_template_params(template_content),
                    'templateContent': template_content
                }
                # create the template
                logger.info('Creating template "{}"'.format(template_name))
                logger.debug(params)
                response = self.dnac.configuration_templates.create_template(**params)
                results['created'] += 1
            else:
                # check if content changed
                if template_content == current_template.templateContent:
                    logger.info('No change in template "{}", no update needed'.format(template_name))
                    # mark it so we don't delete it at the end
                    pushed_templates.append(template_name)
                    results['skipped'] += 1
                    continue

                logger.info('Updating template "{}"'.format(template_name))
                params = {
                    'id': current_template.id,
                    'projectId': self.template_project_id,
                    'name': template_name,
                    'language': current_template.language,
                    'composite': current_template.composite,
                    'softwareType': current_template.softwareType,
                    'deviceTypes': current_template.deviceTypes,
                    'templateParams': self.get_template_params(template_content),
                    'templateContent': template_content
                }
                logger.debug(params)
                response = self.dnac.configuration_templates.update_template(current_template.id, **params)
                results['updated'] += 1

            # check task and retrieve the template_id
            template_id = self.wait_and_check_status(response)
            if not template_id:
                raise Exception('Creation of template "{}" failed'.format(template_name))

            # Commit the template
            response = self.dnac.configuration_templates.version_template(
                templateId=template_id,
                comments='committed by gitlab-ci at {} UTC'.format(datetime.utcnow()))
            self.wait_and_check_status(response)

            pushed_templates.append(template_name)

        # now that we processed all templates, check if there are any
        # templates left on DNAC, which we will delete
        for k, v in provisioned_templates.items():
            if k not in pushed_templates:
                if purge is True:
                    logger.info('deleting template "{}"'.format(k))
                    self.dnac.configuration_templates.delete_template(v.id)
                    results['deleted'] += 1
                else:
                    logger.info('Not attempting to purge template "{}"'.format(k))

        if result_json:
            logger.info('Writing results to {}'.format(result_json))
            with open(result_json, 'w') as fd:
                fd.write(json.dumps(results, indent=2) + '\n')
        return errors == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Provision DNAC templates')
    parser.add_argument('--debug', action='store_true', help='print more debugging output')
    parser.add_argument('--config', help='config file to use')
    parser.add_argument('--results', help='save results in json in this file (default: no file is created)')
    parser.add_argument('--nopurge', action="store_true", help='Don\'t delete templates found on DNAC which are not in the repo')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    service = DNACTemplate(config_file=args.config)
    result = service.provision_templates(purge=not args.nopurge, result_json=args.results)
    sys.exit(0 if result else 1)
