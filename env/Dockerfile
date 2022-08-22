FROM python:3.6

COPY requirements.txt /tmp/requirements.txt
RUN pip install -U pip
RUN pip install -r /tmp/requirements.txt && rm -f /tmp/requirements.txt
RUN apt-get update && apt-get install git
RUN cd / \
	&& git init \
	&& git remote add origin https://gitlab.com/imanassypov/dnac-template-as-code.git \
	&& git fetch \
	&& git checkout master -f
