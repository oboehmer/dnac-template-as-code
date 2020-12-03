# Cisco DNA-Center Template Maintenance and Deployment via a CICD pipeline

This repository contains a simple approch to maintain a Cisco DNA-Center (DNAC) template project and deploy templates on DNAC-managed devices, all using a CICD pipeline.

## Requirements & Caveats

This proof-of-concept code currently assumes DNAC API version 2.1.2.

There are several template values (like device type, software family) which are hardcoded. Right now the pipeline practically only works for Routers and Switches running IOS-XE, however this limitation can easily be lifted.

## Overview
We are maintaing two types of data in the Git repository:

**DNAC configuration templates** (Jinja2 or Velocity) within a dedicated Template Programmer Project in [dnac-templates/](dnac-templates/)

**Deployment instructions** for some or all of the templates in [deployment/](deployment/), where template deployment is controlled through a yaml file which specifies the devices the template should be applied to and which parameters should be used.  
Deployment files can also reference test templates to render deployment-/environment-specific test cases which are executed after deployment.  
Multile depoloyment directories can be used, here we use a deployment-preprod/ directory to control deployment in non-master branches where we want to deploy into a test or pre-production envirnment.

The [scripts/](scripts/) directory contains the DNACTemplate.py python module which implements most of the heavy lifting. Individual scripts in this directory (i.e. provision_templates.py, deploy_templates.py, etc.) are invoked within the pipeline, leveraging DNACTemplate python class to do their respective job.

Post-deployment tests can be specified in [tests/](tests/), we currently use [Robotframework](https://robotframework.org/) along with Cisco's [pyATS](https://developer.cisco.com/pyats/) robot keywords to perform device-level tests.  
In order to validate the specific template deployments, those tests can be rendered using Jinja2 templates in [tests/templates/](tests/templates/).

## Configuration

Configuration items like DNAC endpoint, credentials, DNAC template project name and some other data like WebexTeams notification details is stored in yaml files. We maintain different config files for master-branch (config.yaml) and non-master branches (config-preprod.yaml). This will enable you to use different environments, like prod and preprod.

Configuration items can reference environment variables (i.e. `password: '%ENV{DNAC_PASSWORD}'`), useful to keep password credentials or other sensitive value out of the git repo.

The pipeline (as defined in .gitlab-ci.yaml) assumes a few variables to be set in the gitlab Runner's environment:
- `RUNNER_IMAGE`, set to docker image, see <scripts/Dockerfile> for the build we're using in the demo
- `WEBEX_API_NOTIFICATION_TOKEN`, a webex bot authentication token for notification.

## Pipeline Steps

In order to use different options (like configuration file, directories, etc.), each pipeline step first invokes the `vars.sh` script which sets variables later referenced when invoking the scripts.

#### 1. Validate

It is critical to validate the input before any actions to catch input errors early. In this project, we only perform a basic syntactic validation of the Jinja and YAML files. No serious semantic validation is done, like checking if the configured values match the intended schema (i.e. valid vlan IDs or IP addresses).

#### 2. Provision Template

This step provisions the templates in dnac-templates/ into a DNAC project. The step pushes all dnac-templates into the DNAC project folder, and will also remove all templates therein which are no longer in the repo. This allows you to delete templates via the git/CICD-process as well.

#### 3. Preview and Deploy Template

This step deploys templates, as configured in yaml files in the deployment directory. Please note that repeated execution of the pipeline will also trigger repeated deployment of the templates, so please keep this in mind when writing the templates (like doing a `no access-list xxx` before re-applying the access-list).

This step also renderes a preview of the templates (using DNAC's preview template feature). Please note that the preview is not complete as DNAC inventory data is not available for this step.

#### 4. Testing

To support proper post-deployment testing, the pipeline renders a set of Robotframework test suites based on the deployment YAML files used in the previous step. Once rendered, the tests are executed.  
Device credentials and reachability information need to be pre-configured in pyATS testbed.yaml files, a possible enhancement would be for those to be automatically generated based on DNAC inventory.

#### 5. Notification

Pipeline results are sent to a WebEx Teams room (in master) or to the person pushing the change (non-master), these settings are controlled through config.yaml files.
The notifcation also includes the results of the preview template as well as the log.html created during the previous testing step.