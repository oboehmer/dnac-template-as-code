# Cisco DNA-Center Template Maintenance and Deployment via a CICD pipeline

Cisoc DNA-Center (DNAC) enables Network automation through Device or Config templates. These templates can be edited and applied through DNAC's User Interface or its API.  
This repository contains a simple approch to maintain a set of Cisco DNA-Center (DNAC) templates (within a so-called _Template Project_) through GIT (hence the name "Template as Code"), so all changes to these templates in this Git repo are synced to DNAC.

The project also supports the application of these templates on DNAC-managed devices, including an option to validate proper function of the underlying function.

A recorded demo of this project and a sample use case was presented in the **CiscoLive 2021** session [NetDevOps - CI/CD with Cisco DNA Center Templates as Code - BRKEMT-2007](https://www.ciscolive.com/global/on-demand-library.html#/session/16106298357930015pDT).

## Setup and Sample Workflow

To illustrate the concept, here is a sample setup and workflow:

### Setup Step 1: Set up your template project and create templates

We create a new DNAC Template Configuration Project which contains a number of functions or features we want to automate. In this repo example, this project is called _CICD-CLEUR21_ (as defined in [scripts/config.yaml](scripts/config.yaml)).

> **WARNING**: We recommend to create a new project for this exercise. if you do want to maintain an existing DNAC project through git, please make sure to first download all templates in the DNAC project folder and place them, using the same name, into the Git repo (into dnac-templates/ folder). **Otherwise the templates stored in the DNAC project will be removed on DNAC.**

This project will now be **authoratively and exclusively** managed by this Git workflow, any changes need to be made through git commits, changes made directly on DNAC will be overwritten (and templates created on DNAC missing in the git repo will be removed).

Configure DNAC endpoint information and credentials in [scripts/config.yaml](scripts/config.yaml).

Ceate a set of Jinja2 templates in the [dnac-templates/](dnac-templates/) directory, for example templates to deploy new Vlans or interfaces or other tasks which are not covered by DNAC's existing workflows.

These templates can (and typically will) contain variables which are set when being deployed. To populate the variables, we use so-called _Deployment Files_, which are defined in the next step.

### Setup Step 2: Set up template deployment information

Templates by themselves don't provide much value until they are deployed. This project shows an approach where the deployment information is also stored in Git, for example the Vlan names or IP addresses or other information (this might be not practical for all deployment variables, e.g. IP addresses, which are typically maintained in dedicated IPAM systems, but this project doesn't claim to be production-ready :-)).

Deployment information is stored in the folder [deployment/](deployment/) as YAML files. An example yaml file is shown here:

```yaml
template_name: mgmt-loopback
test_template: loopback-tests.j2

params:
  id: 99
  descr: Management loopback

devices:
  berlab-c9300-3:
    params:
      ipv4: 172.31.1.3
      ipv6: fd00:c1cd:2::3
  berlab-c9300-9.berlab.de:
    params:
      ipv4: 172.31.1.9
```

Deployment files include the name of the template (`template_name`) and a list of devices where the template should be applied (under `devices`). Parameters which defines the variables can be defined globally and is applied to all devices, and/or individually per devices as part of the `params` sections. Please refer to [deployment/README.md](deployment/README.md) for more information.

You can optionally also render test cases which are executed post deployment to validate the proper function of the configuration via the `test_template` parameter in the deployment YAML file, please refer to [tests/README.md](tests/README.md) for more information.


### Sample Workflow

With a properly created template, we can now maintain both the template as well as the parameters used to apply the template on the desired devices merely by committing the changes into git. These changes will trigger a pipeline (as described [below](#pipeline-steps) which validates and updates the template on DNAC and optionally deploys it, followed my running tests on the devices (if test templates have been defined). Notification of the pipeline's result (success or failure) are sent via WebEx. 

## Requirements & Caveats


This is proof-of-concept code and has a set of caveats, listed below:

- It requires DNAC API version 2.1.2
- We support only a single DNAC Template Project (well, actually two, one for production/deployment, and one for staging/pre-deployment)
- There are several template values (like device type, software family) which are hardcoded. Right now the pipeline practically only works for Routers and Switches running IOS-XE, however this limitation can easily be lifted through modification of the scripts.
- We demonstrate the pipeline running on Gitlab-CI, however it should be easy to port it to Github-Actions, Jenkins or other CICD tools.

## Tool Overview
We are maintaing two types of data in the Git repository:

**DNAC configuration templates** (Jinja2 or Velocity) within a dedicated Template Programmer Project in [dnac-templates/](dnac-templates/)

**Deployment instructions** for some or all of the templates in [deployment/](deployment/), where template deployment is controlled through a yaml file which specifies the devices the template should be applied to and which parameters should be used.  
Deployment files can also reference test templates to render deployment-/environment-specific test cases which are executed after deployment.  
Multile depoloyment directories can be used, here we use a deployment-preprod/ directory to control deployment in non-main branches where we want to deploy into a test or pre-production envirnment.

The [scripts/](scripts/) directory contains the DNACTemplate.py python module which implements most of the heavy lifting. Individual scripts in this directory (i.e. provision_templates.py, deploy_templates.py, etc.) are invoked within the pipeline, leveraging DNACTemplate python class to do their respective job.

Post-deployment tests can be specified in [tests/](tests/), we currently use [Robotframework](https://robotframework.org/) along with Cisco's [pyATS](https://developer.cisco.com/pyats/) robot keywords to perform device-level tests.  
In order to validate the specific template deployments, those tests can be rendered using Jinja2 templates in [tests/templates/](tests/templates/).

## Configuration

Configuration items like DNAC endpoint, credentials, DNAC template project name and some other data like WebexTeams notification details is stored in yaml files. We maintain different config files for main-branch (config.yaml) and non-main branches (config-preprod.yaml). This will enable you to use different environments, like prod and preprod.

Configuration items can reference environment variables (i.e. `password: '%ENV{DNAC_PASSWORD}'`), useful to keep password credentials or other sensitive value out of the git repo.

The pipeline (as defined in .gitlab-ci.yaml) assumes a few variables to be set in the gitlab Runner's environment:
- `RUNNER_IMAGE`, set to docker image, see <scripts/Dockerfile> for the docker image we're using in the demo
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

Pipeline results are sent to a WebEx Teams room (in main) or to the person pushing the change (non-main), these settings are controlled through config.yaml files.
The notifcation also includes the results of the preview template as well as the log.html created during the previous testing step.