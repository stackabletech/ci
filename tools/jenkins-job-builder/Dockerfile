FROM python:3

# install required Python modules
COPY python_modules /
RUN pip install --no-cache-dir -r python_modules

# install OS packages
RUN apt-get update
RUN apt-get install curl -y

# install Helm and the Stackable Helm repos
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -s -
RUN helm repo add stackable-dev https://repo.stackable.tech/repository/helm-dev/
RUN helm repo add stackable-stable https://repo.stackable.tech/repository/helm-stable/
RUN helm repo add stackable-test https://repo.stackable.tech/repository/helm-test/
RUN helm repo update

# copy jjb files
COPY jjb/ /jjb/
COPY catalog/ /catalog/

# copy main Python script
COPY *.py /

ENV GIT_BRANCH_OR_TAG=hurz

ENTRYPOINT [ "python", "/jenkins-job-builder.py" ]
