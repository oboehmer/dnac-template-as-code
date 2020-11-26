#!/usr/bin/env python
import json
import logging
import os
import re
import time
from datetime import datetime
from attrdict import AttrDict

import urllib3
import yaml
from dnacentersdk import api, ApiError

from utils import read_config

urllib3.disable_warnings()
logger = logging.getLogger(os.path.basename(__file__))


class DNACTemplate(object):

    def __init__(self, config_file=None, project=None):
        # read config file
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config = read_config(config_file)
        # login to DNAC
        try:
            self.dnac = api.DNACenterAPI(**self.config.dnac)
        except ApiError:
            logger.fatal('Can\'t connect to DNAC, please check the configuration: {}'.format(
                self.config.dnac))
            raise
        # get project id, create project if needed
        self.template_project = project or self.config.template_project
        self.template_project_id = self.get_project_id(self.template_project)

    def get_project_id(self, project):
        '''
        Retrieve the project ID as we need it in various places. If
        Project doesn't exist, create it
        '''
        if not project:
            raise ValueError('DNAC project name not provided in config.yaml')

        for p in self.dnac.configuration_templates.get_projects():
            if p.name == project:
                return p.id

        task = self.dnac.configuration_templates.create_project(name=project)
        project_id = self.wait_and_check_status(task)
        if project_id:
            logger.info('Created project "{}"'.format(project))
            return project_id
        else:
            raise Exception('Creation of project "{}" failed'.format(project))

    def retrieve_provisioned_templates(self, template_name=None):
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
            # logger.debug('Retrieved template {}, full info: {}'.format(t.templateId, result[t.name]))
        return result

    def retrieve_template_id_by_name(self, template_name):
        '''
        Retrieves template by name in selected project
        '''
        for t in self.dnac.configuration_templates.gets_the_templates_available(
                project_id=self.template_project_id):
            if t.name == template_name:
                return t.templateId
        return None

    def get_template_params(self, content, language):
        '''
        extracts referenced jinja2 variables and returns params list.
        '''
        # TODO: This is not robust, we assume all variables found are strings,
        # we don't look for vars in Jinja control statements or loops
        # as we don't seem to need this stored in the templates, just return
        # []

        # return []
        if language == 'JINJA':
            from jinja2 import Environment, PackageLoader, meta
            env = Environment(loader=PackageLoader('gummi', 'templates'))
            parsed_content = env.parse(content)
            variables = meta.find_undeclared_variables(parsed_content)
        else:
            variables = re.findall(r'\${*([a-z][a-z0-9_]+)}*', content, re.I)
        params = []
        order = 1
        for v in variables:
            if not v.startswith('__'):
                # ignore internal variables
                params.append({
                    'parameterName': v,
                    'dataType': 'STRING',
                    'required': False,
                    'order': order,
                    'customOrder': 0})
                order += 1
            # d ={'parameterName': 'password', 'dataType': 'STRING', 'defaultValue': None,
            # 'description': None, 'required': True, 'notParam': False, 'paramArray': False,
            # 'displayName': None, 'instructionText': None, 'group': None, 'order': 2,
            # 'customOrder': 0, 'selection': None, 'range': [], 'key': None, 'provider':
            # None, 'binding': '', 'id': '869b0b95-8831-4e9e-9480-5268755bb270'}

        return params

    def wait_and_check_status(self, response, max_attempts=2, sleeptime=2):
        '''
        poll status of task (i.e. template creation or update), and return
        response.data
        '''
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

    def get_template_langauge(self, content):
        '''
        simple heuristic to determine if we deal with a jinja or velocity (default)
        template
        '''
        is_jinja = ('{{' in content and '}}' in content) or \
                   ('{%' in content and '%}' in content)
        is_velocity = (re.search(r'\$[A-Z]+', content) is not None)

        if is_jinja and is_velocity:
            return 'VELOCITY'
        elif is_jinja:
            return 'JINJA'
        else:
            return 'VELOCITY'

    def provision_templates(self, template_dir, purge=True, result_json=None):
        '''
        Push all templates found in our git repo to DNAC
        TODL Templates which have previously provisioned but which have been removed
        on git are also removed from DNAC
        '''
        results = {
            'message': 'DNAC template provisioning run from {} UTC'.format(datetime.utcnow()),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'deleted': 0,
            'errors': 0,
        }

        # first remember which customers are currently provisioned so we can
        # handle deletion of the whole customer file
        provisioned_templates = self.retrieve_provisioned_templates()
        if len(provisioned_templates) > 0:
            logger.debug('provisioned templates: {}'.format(', '.join(provisioned_templates.keys())))
            # for t in provisioned_templates.values():
            #     logger.debug(t)
        else:
            logger.debug('no templates provisioned.')

        pushed_templates = []

        # process all the templates found in the repo
        for template_file in os.listdir(template_dir):
            if template_file.startswith('.'):
                continue

            logger.debug('processing file "{}"'.format(template_file))

            with open(os.path.join(template_dir, template_file), 'r') as fd:
                template_content = fd.read()
                template_content = re.sub('__PROJECT__', self.template_project, template_content)

            template_name = template_file

            language = self.get_template_langauge(template_content)

            current_template = provisioned_templates.get(template_name)
            if not current_template:
                # new template
                params = {
                    'project_id': self.template_project_id,
                    'name': template_name,
                    'description': '',
                    'containingTemplates': [],
                    'language': language,
                    'composite': False,
                    'deviceTypes': [{'productFamily': 'Routers'}, {'productFamily': 'Switches and Hubs'}],
                    'softwareType': "IOS-XE",
                    'softwareVersion': None,
                    'tags': [],
                    'templateParams': self.get_template_params(template_content, language),
                    'templateContent': template_content
                }
                # create the template
                logger.info('Creating template "{}"'.format(template_name))
                logger.debug(params)
                try:
                    response = self.dnac.configuration_templates.create_template(**params)
                except ApiError as e:
                    logger.error(str(e))
                    results['errors'] += 1
                    continue
                else:
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
                    'language': language,
                    'composite': current_template.composite,
                    'softwareType': current_template.softwareType,
                    'deviceTypes': current_template.deviceTypes,
                    # 'templateParams': self.get_template_params(template_content, language),
                    'templateParams': current_template.templateParams,
                    'templateContent': template_content
                }
                logger.debug(params)
                try:
                    response = self.dnac.configuration_templates.update_template(current_template.id, **params)
                except ApiError as e:
                    logger.error(str(e))
                    results['errors'] += 1
                    continue
                else:
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

        return results['errors'] == 0

    def _log_preview(self, msg, fd=None):
        logger.info(msg)
        if fd:
            fd.write(msg + '\n')

    def preview_templates(self, dir_or_file, preview_file=None):

        if preview_file:
            fd = open(preview_file, 'a+')
        else:
            fd = None

        try:
            rc = self.deploy_templates(dir_or_file, result_json=None, preview_fd=fd, preview=True)
        finally:
            if fd:
                fd.close()

        return rc

    def deploy_templates(self, dir_or_file, result_json=None, preview_fd=None, preview=False):
        '''
        deploy the templates in template_dir based on yaml files
        in dir_or_file (or use a single file)
        If preview is True, just preview the template (no deployment)
        '''

        deployment_results = {
            'message': 'DNAC template deployment run from {} UTC'.format(datetime.utcnow()),
            'templates_processed': 0,
            'devices_configured': 0,
            'deployment_failures': 0,
        }

        if os.path.isdir(dir_or_file):
            files = [os.path.join(dir_or_file, f)
                     for f in os.listdir(dir_or_file)
                     if not f.startswith('.')]
        else:
            files = [dir_or_file]

        for f in files:

            logger.info('processing {}'.format(f))
            with open(f) as fd:
                dep_info = AttrDict(yaml.safe_load(fd.read()))

            try:
                template_name = dep_info.template_name
            except AttributeError:
                template_name = os.path.splitext(os.path.split(f)[1])[0]

            template_id = self.retrieve_template_id_by_name(template_name)
            assert template_id, 'Can\'t retrieve template {} in project {}'.format(
                template_name, self.template_project)

            logger.debug('Using template {}/{}'.format(template_name, template_id))

            # set up global vars for this deployment
            if hasattr(dep_info, 'params'):
                assert isinstance(dep_info['params'], dict), \
                    'params in deployment file {} must be yaml dictionary'.format(f)
                global_params = dep_info['params']
            else:
                global_params = {}

            # iterate through devices configured, we provision all devices in one shot,
            # so collect the target_info
            target_info = []
            for device, items in dep_info.devices.items():

                if items and 'params' in items:
                    assert isinstance(items['params'], dict), \
                        '{}.params in deployment file {} must be yaml dictionary'.format(device, f)
                    # update the variable assignment per device
                    params = global_params.copy()
                    params.update(items['params'])
                else:
                    params = global_params

                target_info.append({'id': device, 'type': "MANAGED_DEVICE_HOSTNAME", "params": params})

            logger.debug('Target Info collected: {}'.format(target_info))

            if preview:
                for t in target_info:
                    self._log_preview('# rendering template {} for device {}, params: {}'.format(
                        template_name, t['id'], t['params']),
                        preview_fd)
                    results = self.dnac.configuration_templates.preview_template(
                        templateId=template_id, params=t['params'])
                    self._log_preview('\n{}\n'.format(results.cliPreview), preview_fd)

                continue

            logger.info('Deploying {} using on devices {}'.format(template_name, ', '.join([d['id'] for d in target_info])))
            deployment_results['templates_processed'] += 1
            deployment_results['devices_configured'] += len(target_info)

            results = self.dnac.configuration_templates.deploy_template(
                forcePushTemplate=True, isComposite=False, templateId=template_id, targetInfo=target_info)
            logger.debug('Deployment request result: {}'.format(results))

            # results returns deployment id within a text blob (sic), so extract
            # {'deploymentId': 'Deployment of  Template: 93dc2023-d61e-4498-b045-bd1599959319.ApplicableTargets: [berlab-c9300-3]Template Deployemnt Id: 42446169-f534-4c7f-b356-52f6b4af7cfa',
            #  'startTime': '', 'endTime': '', 'duration': '0 seconds'}
            # and even typo in the response, double-sic...
            m = re.search(r'Deployemnt Id: ([a-f0-9-]+)', results.deploymentId, re.I)
            if m:
                deployment_id = m.group(1)
            else:
                raise ValueError('Can\'t extract deployment id from API response {}'.format(results.deploymentId))

            # check for status
            i = 0
            while i < 10:
                time.sleep(2)
                results = self.dnac.configuration_templates.get_template_deployment_status(deployment_id=deployment_id)
                logger.debug('deployment status: {}'.format(results))
                if results.status == 'IN_PROGRESS':
                    i += 1
                    continue
                else:
                    break
            logger.info('deployment status: {}'.format(results.status))

            if results.status != 'SUCCESS':
                deployment_results['deployment_failures'] += 1

        if result_json and not preview:
            logger.info('Writing results to {}'.format(result_json))
            with open(result_json, 'w') as fd:
                fd.write(json.dumps(deployment_results, indent=2) + '\n')

        return deployment_results['deployment_failures'] == 0
