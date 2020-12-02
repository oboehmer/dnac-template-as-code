#!/bin/sh
#
# setup vars for cicd pipeline

TEMPLATE_DIR="dnac-templates/"
DEBUG=""
# DEBUG="--debug"

if [ "$CI_BUILD_REF_NAME" == "master" ] ; then 
    CONFIG_YAML="scripts/config.yaml"
    DEPLOY_DIR="deployment/"
    TESTBED="testbed.yaml"
else 
    CONFIG_YAML="scripts/config-preprod.yaml"
    DEPLOY_DIR="deployment-preprod"
    TESTBED="testbed-preprod.yaml"
fi

cat << _EOF
DEBUG=$DEBUG
CONFIG_YAML=$CONFIG_YAML
TEMPLATE_DIR=$TEMPLATE_DIR
DEPLOY_DIR=$DEPLOY_DIR
TESTBED=$TESTBED
_EOF
