FROM python:3

# install required Python modules
COPY python_modules /
RUN pip install --no-cache-dir -r python_modules

# copy jjb files
COPY jjb/ /jjb/
COPY catalog/ /catalog/
COPY templates/ /templates/

# copy main Python script
COPY *.py /

ENTRYPOINT [ "python", "/testing-toolbox.py" ]
