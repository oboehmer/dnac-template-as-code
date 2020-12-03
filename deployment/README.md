# Deployment Directory

The YAML files in this directory control the deployment of a Cisco DNAC template on one or more devices.

The files have the following structure (check the commented example below):

- `template_name`: name of the dnac template (project name must not be mentioned).  
Optional, if ommitted the basename of the deployment file (without extension will be used)
- `test_template`: name of a jinja2 template to render tests for.  
Optional, no tests will be rendered if this parameter is ommitted
- `params`: a dictionary of variable/value items, applied to all devices. Optional
- `devices`: a list of devices where the template needs to be applied on, with optional parameters. The device name needs to match the device name in DNAC.

Here is a an example deployment file:

```
# if template name is not specified, use this file's basename (without .yaml)
template_name: SNMP

# If config/service specific tests cases should be rendered, create a Jinja2 
# template in ../tests/templates and reference its name (without the path here)
test_template: test_template.j2

# Define template parameters which apply to all devices
params:
  var1: value1
  var2: value2

# define the devices where the template should be applied on
#
# you can override the global params above or assign specific 
# vars and values, as shown in device2 below.
# 
#
devices:
  # note that each device entry needs to be a dict, so it needs to end with a ":"
  device_name1:
  device_name2:
    params:
      var1: value2
  #
  # The following entry shows how the same template can be applied multiple
  # times per device, each using different parameter values. Please note that
  # the params value is now a list of dictionaries
  device_name3:
    params:
      - var1: foo1
        var2: bar1
      - var1: foo2
        var2: bar2
 
```

The first pipeline step validates the correct structure of the deployment files, so any errors will be caught.
