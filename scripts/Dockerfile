FROM python:3.6
# install gummi first, it has some strict reqs for request and six which
# are incompatible with other packages
RUN pip install gummi==1.3.3
# remove gummi from the requirements
COPY requirements.txt /tmp/requirements.txt

# inline grep -v '^gummi'
RUN sed -n -i '/^gummi/! p' /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm -f /tmp/requirements.txt
