#!/bin/sh
#
# setup vars for cicd pipeline

TEMPLATE_DIR="dnac-templates/"
DEBUG=""
# DEBUG="--debug"

# https://github.com/example42/psick/issues/273
# Gitlab CI variable CI_BUILD_REF_NAME is deprecated. Rename it to CI_COMMIT_REF_NAME as in future releases it will be removed.
# Note: Starting with GitLab 9.0, we have deprecated the $CI_BUILD_* variables. You are strongly advised to use the new variables as we will remove the old ones in future GitLab releases.

if [ "$CI_COMMIT_REF_NAME" == "master" ] ; then 
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
