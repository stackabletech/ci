FROM python:3

# install required Python modules
COPY python_modules /
RUN pip install --no-cache-dir -r python_modules

# install Replicated CLI
RUN mkdir -p /tmp/replicated/
RUN curl "https://raw.githubusercontent.com/replicatedhq/replicated/master/install.sh" > /tmp/replicated/install.sh
RUN chmod a+x /tmp/replicated/install.sh
RUN /tmp/replicated/install.sh

# copy main Python script
COPY *.py /

ENTRYPOINT [ "python", "/replicated-testrunner.py" ]
