# Post-Deployment Validation

Validating the proper function post-deployment is a critical part of NetDevOps. Our project supports this by rendering test cases using the same set of parameters/variables as the deplokyment templates, so the tests can be tailored to the changes made.

Our demo leverages the OpenSource [RobotFramework](https://robotframework.org/) test framework, using [pyATS/Genie Robot Keywords](https://pubhub.devnetcloud.com/media/genie-docs/docs/userguide/robot/index.html) which facilitate interacting with Cisco and 3rd party devices.

The test cases provided in this repo interact directly with the devices using ssh, the required testbed.yaml files need to be created manually (DNAC API doesn't provide the device credentials, so we can't create them dynamically as part of the pipeline, this is left as an exercise to the reader ;-) ). 

Please refer to test case example templates in the [./templates/](./templates/) subdirectory, the linkage between the deployment information and testcase template is defined in the deployment YAML file (using the `test_template:` parameter).

The tests are rendered as part of the tests pipeline step, or manually via 

```
python scripts/render_tests.py --config scripts/config.yaml --deploy_dir ./deployment --out_dir tests/deploy/
```

You can then run them through robot

```
cd tests
robot --name 'DNAC Template Tests' --outputdir out/ --xunit output-junit.xml --variable testbed:testbed.yaml --extension robot deploy/
```
