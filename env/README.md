# CICD Runner Container & Build Environment

This directory contains the files required to build the Docker container used for the CICD pipeline. 

## Sample Build Commands

Please replace the container name, tag and the docker-repo and path according to your local environment.

```
$ docker build -t dnac-cicd-container:tag -f Dockerfile .
$ docker tag dnac-cicd-container:tag my-docker-repo/path/dnac-cicd-container:tag
$ docker push my-docker-repo/path/dnac-cicd-container:tag
```

## Local Development Environment

Setup a python3 environment (we tested this on python3.6 and 3.7) and install the required dependencies, i.e.:

```
$ python3 -m venv ~/venv/dnactemplates
$ source ~/venv/dnactemplates/bin/activate
$ pip install -r requirements.txt
```
