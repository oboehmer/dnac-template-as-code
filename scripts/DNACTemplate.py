#
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

import logging
import os
import re
import time
from datetime import datetime
from attrdict import AttrDict

import urllib3
import yaml
from dnacentersdk import api, ApiError
from jinja2 import Environment, FileSystemLoader, meta

from utils import read_config, update_results_json

urllib3.disable_warnings()
logger = logging.getLogger(os.path.basename(__file__))


def _basename(path):
    # foo/bar/baz/filename.txt --> filename
    return os.path.splitext(os.path.split(path)[1])[0]


class DNACTemplate(object):

    def __init__(self, config_file=None, project=None, connect=True):
        # read config file
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config = read_config(config_file)
        self.test_template_dir = os.path.join(os.path.dirname(__file__), '../tests/templates')
        if connect is False:
            return

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

    def get_template_params(self, content, language, template_dir):
        '''
        extracts referenced jinja2 variables and returns params list.
        '''
        # TODO: This is not robust, we assume all variables found are strings,
        # we don't look for vars in Jinja control statements or loops
        # as we don't seem to need this stored in the templates, just return
        # []

        # return []
        if language == 'JINJA':
            env = Environment(loader=FileSystemLoader(template_dir))
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
        else:
            logger.debug('no templates provisioned.')

        pushed_templates = []

        # process all the templates found in the repo
        for template_file in os.listdir(template_dir):
            if template_file.startswith('.') or 'README.md' in template_file:
                continue

            logger.debug('processing file "{}"'.format(template_file))
            with open(os.path.join(template_dir, template_file), 'r') as fd:
                template_content = fd.read()
                # DNAC requires includes to include the absolute path, so we make this
                # dependent on the project (i.e. {% include "__PROJECT__/foo" %} )
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
                    'templateParams': self.get_template_params(template_content, language, template_dir),
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

                params = {
                    'id': current_template.id,
                    'projectId': self.template_project_id,
                    'name': template_name,
                    'language': language,
                    'composite': current_template.composite,
                    'softwareType': current_template.softwareType,
                    'deviceTypes': current_template.deviceTypes,
                    'templateParams': self.get_template_params(template_content, language, template_dir),
                    'templateContent': template_content
                }
                logger.info('Updating template "{}"'.format(template_name))
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
            update_results_json(
                filename=result_json,
                message='Template provisioning run',
                stats=results)

        return results['errors'] == 0

    def parse_deployment_file(self, deployment_file):
        '''
        Parses a deployment file and returns the contents in a structure
        with all device params expanded (i.e. global params applied to each
        device params dict)
        '''
        logger.info('processing {}'.format(deployment_file))
        with open(deployment_file) as fd:
            result = yaml.safe_load(fd.read())

        if not result or not isinstance(result, dict):
            raise ValueError('{} does not look like a YAML file'.format(deployment_file))

        if 'template_name' not in result:
            result['template_name'] = _basename(deployment_file)

        # set up global vars for this deployment
        if 'params' in result:
            assert isinstance(result['params'], dict), \
                'params in deployment file {} must be yaml dictionary'.format(deployment_file)
            global_params = result['params']
        else:
            global_params = {}

        # iterate through devices configured
        for device, items in result['devices'].items():
            if items is None:
                # in case no params defined under device
                result['devices'][device] = {}
            result['devices'][device]['name'] = device

            if items and 'params' in items:
                # we can define a single var/value dict for device,
                # or a list of var/value dicts in which case the template
                # will be applied multiple times with different values
                params = []
                if isinstance(items['params'], dict):
                    param_list = [items['params']]
                elif isinstance(items['params'], list):
                    param_list = items['params']
                elif items['params'] is None:
                    # allow to remove global params with an empty param list
                    param_list = [{}]
                else:
                    raise ValueError('{} params need to be dict, list or None'.format(device))
                # update the variable assignment per device
                for i, p in enumerate(param_list):
                    params.append(global_params.copy())
                    params[i].update(p)
            else:
                params = [global_params]
            result['devices'][device]['params'] = params

        logger.debug('parse_deployment_file() returns: {}'.format(result))
        return AttrDict(result)

    def _log_preview(self, msg, fd=None, facility='info'):
        getattr(logger, facility)(msg)
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
            'deployment_runs': 0,
            'devices_configured': 0,
            'deployment_failures': 0,
        }

        if os.path.isdir(dir_or_file):
            files = [os.path.join(dir_or_file, f)
                     for f in os.listdir(dir_or_file)
                     if not f.startswith('.') and (f.endswith('.yaml') or f.endswith('.yml'))]
        else:
            files = [dir_or_file]

        for f in files:

            dep_info = self.parse_deployment_file(f)

            template_id = self.retrieve_template_id_by_name(dep_info.template_name)
            assert template_id, 'Can\'t retrieve template {} in project {}'.format(
                dep_info.template_name, self.template_project)
            logger.debug('Using template {}/{}'.format(dep_info.template_name, template_id))

            all_targets = []
            for device, items in dep_info.devices.items():
                for p in items['params']:
                    all_targets.append({'id': device, 'type': 'MANAGED_DEVICE_HOSTNAME', 'scope': 'RUNTIME', 'params': p})
            logger.debug('Target Info collected: {}'.format(all_targets))

            devices_configured = {}

            for target_info in all_targets:

                if preview:
                    self._log_preview('# rendering template {} for device {}, params: {}'.format(
                        dep_info.template_name, target_info['id'], target_info['params']),
                        preview_fd)
                    results = self.dnac.configuration_templates.preview_template(
                        templateId=template_id, params=target_info['params'])
                    if results.cliPreview is None:
                        errors = getattr(results, 'validationErrors', [])
                        msg = ''
                        for e in errors:
                            msg += ':'.join(str(i) for i in e.values()) + "\n  "
                        self._log_preview('\nERROR: {}\n'.format(msg), preview_fd, facility='error')
                    else:
                        self._log_preview('\n{}\n'.format(results.cliPreview), preview_fd)

                else:
                    logger.info('Deploying {} using params {} on device {}'.format(
                        dep_info.template_name, target_info['params'], target_info['id']))
                    logger.debug('Target Info: {}'.format(target_info))

                    deployment_results['deployment_runs'] += 1
                    devices_configured[target_info['id']] = 1

                    results = self.dnac.configuration_templates.deploy_template(
                        forcePushTemplate=True, isComposite=False,
                        templateId=template_id, targetInfo=[target_info])
                    logger.debug('Deployment request result: {}'.format(results))

                    # results returns deployment id within a text blob (sic), so extract
                    # {'deploymentId': 'Deployment of  Template:
                    # 93dc2023-d61e-4498-b045-bd1599959319.ApplicableTargets:
                    # [berlab-c9300-3]Template Deployemnt Id: 42446169-f534-4c7f-b356-52f6b4af7cfa',
                    #  'startTime': '', 'endTime': '', 'duration': '0 seconds'}
                    # and even typo in the response, double-sic...
                    m = re.search(r'Deployemnt Id: ([a-f0-9-]+)', results.deploymentId, re.I)
                    if m:
                        deployment_id = m.group(1)
                    else:
                        raise ValueError('Can\'t extract deployment id from API response {}'.format(
                            results.deploymentId))

                    # check for status
                    i = 0
                    while i < 10:
                        time.sleep(2)
                        results = self.dnac.configuration_templates.get_template_deployment_status(
                            deployment_id=deployment_id)
                        logger.debug('deployment status: {}'.format(results))
                        if results.status in ('IN_PROGRESS', 'INIT'):
                            i += 1
                            continue
                        else:
                            break
                    logger.info('deployment status: {}'.format(results.status))

                    if results.status != 'SUCCESS':
                        logger.error('Deployment error on device {}:\n{}'.format(
                            target_info['id'], results.devices[0].detailedStatusMessage))
                        deployment_results['deployment_failures'] += 1

        if result_json and not preview:
            deployment_results['devices_configured'] = len(devices_configured)
            logger.info('Writing results to {}'.format(result_json))
            update_results_json(
                filename=result_json,
                message='Template deployment run',
                stats=deployment_results)

        return deployment_results['deployment_failures'] == 0

    def render_tests(self, dir_or_file, out_dir, template_dir=None):
        '''
        render tests from deployment files
        Use the same params structure used to preview/apply templates,
        but render jinja2 templates kept in template_dir
        '''
        if not template_dir:
            template_dir = self.test_template_dir

        try:
            os.mkdir(out_dir)
        except FileExistsError:
            pass

        if os.path.isdir(dir_or_file):
            files = [os.path.join(dir_or_file, f)
                     for f in os.listdir(dir_or_file)
                     if not f.startswith('.') and (f.endswith('.yaml') or f.endswith('.yml'))]
        else:
            files = [dir_or_file]

        for f in files:

            dep_info = self.parse_deployment_file(f)

            if 'test_template' not in dep_info:
                logger.debug('no test_template referenced in {}, skipping'.format(f))
                continue

            template_file = os.path.join(template_dir, dep_info.test_template)
            with open(template_file) as fd:
                content = fd.read()

            template = Environment(loader=FileSystemLoader(template_dir)).from_string(content)

            # populate device list for Jinja2 rendering. As we might have multiple params
            # dicts per device (we can apply the same template multiple times with different params)
            # we append this device multiple times (each with different params) for Jinja so the
            # test template author doesn't have to worry about this
            devices = []
            for dev, items in dep_info.devices.items():
                for p in items['params']:
                    devices.append({'name': dev, 'params': p})

            test_content = template.render(devices=devices)
            logger.debug('Rendering {} produced:\n{}'.format(dep_info.test_template, test_content))

            robot_file = '{}/{}_{}.robot'.format(
                out_dir,
                _basename(dep_info.test_template),
                _basename(f))
            logger.info('Creating {}'.format(robot_file))
            with open(robot_file, 'w') as fd:
                fd.write(test_content)

        return True
