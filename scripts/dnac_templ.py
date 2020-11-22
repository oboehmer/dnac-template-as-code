#!/usr/bin/env python
import argparse
from datetime import datetime
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
        self.template_project_id = self.get_project_id()

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

    def get_project_id(self):
        '''
        Retrieve the project ID as we need it in various places
        '''
        for p in self.dnac.configuration_templates.get_projects():
            if p.name == self.config.template_project:
                return p.id
        raise Exception('template_project not found on DNAC')

    def retrieve_provisioned_templates(self):
        '''
        retrieve a list of Jinja2 templates currently provisioned.
        Returns a dict of template detail dicts, indexed by name
        '''
        logger.debug('Retrieving existing templates')
        result = {}
        for t in self.dnac.configuration_templates.gets_the_templates_available(
                project_id=self.template_project_id):
            # store both template and template details, joining both in the
            # same dict
            result[t.name] = t
            result[t.name].update(self.dnac.configuration_templates.get_template_details(t.templateId))
            logger.debug('Retrieved template {}, full info: {}'.format(t.templateId, result[t.name]))
        return result

    def _retrieve_variables(self, content):
        # TODO
        from jinja2 import Environment, PackageLoader, meta
        env = Environment(loader=PackageLoader('gummi', 'templates'))
        parsed_content = env.parse(content)
        meta.find_undeclared_variables(parsed_content)
        breakpoint()

    def get_template_params(self, content):
        # TODO
        # self._retrieve_variables(content)
        return []

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

    def provision_templates(self):
        '''
        Push all templates found in our git repo to DNAC
        TODL Templates which have previously provisioned but which have been removed
        on git are also removed from DNAC
        '''
        errors = 0

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
            logger.debug('processing file ' + template_file)

            with open(os.path.join(self.template_dir, template_file), 'r') as fd:
                template_content = fd.read()

            # self.get_template_params(template_content)
            # continue
            #

            current_template = provisioned_templates.get(template_file)
            if not current_template:
                # new template
                params = {
                    'project_id': self.template_project_id,
                    'name': template_file,
                    'language': 'JINJA',
                    'composite': False,
                    'deviceTypes': [{'productFamily': 'Switches and Hubs'}],
                    'softwareType': "IOS-XE",
                    'templateParams': self.get_template_params(template_content),
                    'templateContent': template_content
                }
                # create the template
                logger.info('Creating template {}'.format(template_file))
                logger.debug(params)
                response = self.dnac.configuration_templates.create_template(**params)

            else:
                # check if content changed
                if template_content == current_template.templateContent:
                    logger.info('No change in template {}, no update needed'.format(template_file))
                    # mark it so we don't delete it at the end
                    pushed_templates.append(template_file)
                    continue

                logger.info('Updating template {}'.format(template_file))
                params = {
                    'id': current_template.id,
                    'projectId': self.template_project_id,
                    'name': template_file,
                    'language': current_template.language,
                    'composite': current_template.composite,
                    'softwareType': current_template.softwareType,
                    'deviceTypes': current_template.deviceTypes,
                    # 'templateParams': self.get_template_params(template_content),
                    'templateParams': current_template.templateParams,
                    'templateContent': template_content
                }
                logger.debug(params)
                response = self.dnac.configuration_templates.update_template(current_template.id, **params)

            # check task and retrieve the template_id
            template_id = self.wait_and_check_status(response)
            if not template_id:
                raise Exception('Creation of template {} failed'.format(template_file))

            # Commit the template
            response = self.dnac.configuration_templates.version_template(
                templateId=template_id,
                comments='committed by gitlab-ci at {} UTC'.format(datetime.utcnow()))
            self.wait_and_check_status(response)

            pushed_templates.append(template_file)

        # now that we processed all templates, check if there are any
        # templates left on DNAC, which we will delete
        for k, v in provisioned_templates.items():
            if k not in pushed_templates:
                logger.info('deleting template {}'.format(k))
                self.dnac.configuration_templates.delete_template(v.id)

        return errors == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Provision DNAC templates')
    parser.add_argument('--debug', action='store_true', help='print more debugging output')
    parser.add_argument('--config', help='config file to use')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    service = DNACTemplate(config_file=args.config)
    result = service.provision_templates()
    sys.exit(0 if result else 1)
