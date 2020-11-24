# DNAC Template Maintenance via CICD pipeline

This repository contains a simple approch to maintain a DNA-Center template
project using a CICD pipeline.

## Requirements & Caveats

This proof-of-concept code currently assumes DNAC API version 2.1.2.

There are several template values (like device type, software family) which are hardcoded. Right now the pipeline practically only works for Routers and Switches running IOS-XE.

## Overview
We are maintaing two types of data in the Git repository:

- DNAC configuration templates (Jinja2 or Velocity) within a dedicated Template Programmer Project in [dnac-templates/](dnac-templates/)
- Deployment information for some or all of the templates in [deployment/](deployment/), where each template's deployment is controlled through a yaml file which specifies the devices the template should be applied to and which parameters should be used

Any changes to the aforementioned data will trigger a (re-)deployment of the templates into the project, and, when run in "master" branch, also a (re-)deployment on the devices configured.

## Configuration

Configuration items like DNAC endpoint, credentials, DNAC template project name and some other data is stored in yaml files. We maintain different config files for master-branch (config.yaml) and non-master branches (config-preprod.yaml). This will enable you to use different environments, like prod and preprod.

Configuration items can reference environment variables (i.e. `password: '%ENV(DNAC_PASSWORD)'`), useful to keep password credentials out of the git repo.

The pipeline assumes a few variables to be set in the gitlab Runner's environment:
- `RUNNER_IMAGE`, set to docker image, see <scripts/Dockerfile> for the build we're using in the demo
- `WEBEX_API_NOTIFICATION_TOKEN`, a webex bot authentication token for notification

## Pipeline Steps

#### 1. Validate

It is critical to validate the input before any actions. In this project, we only perform a basic syntactic validation of the Jinja and YAML files. No additional validation is done

#### 2. Provision Template

This step provisions the templates in dnac-templates/ into a DNAC project. The step pushes all dnac-templates into the DNAC project folder, and will also remove all templates therein which are no longer in the repo. This allows you to delete templates via the git/CICD-process as well.

#### 3. Deploy Template (master-only)

This step deploys templates, as configured in yaml files in the deployment directory. Please note that repeated execution of the pipeline will also trigger repeated deployment of the templates, so please keep this in mind when writing the templates (like doing a `no access-list xxx` before re-applying the access-list)

#### 4. Testing

This step is not finalized, we are executing a few basic Robotframework tests using pyATS keywords.

#### 5. Notification

Pipeline results are sent to a WebEx Teams room (in master) or to the person pushing the change (non-master). Notification settings can also be controlled using config.yaml.

