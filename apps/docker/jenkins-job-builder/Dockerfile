FROM python:3

# install required Python modules
COPY python_modules /
RUN pip install --no-cache-dir -r python_modules

# install Helm and the Stackable Helm repos
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -s -
RUN helm repo add stackable-dev https://repo.stackable.tech/repository/helm-dev/
RUN helm repo add stackable-stable https://repo.stackable.tech/repository/helm-stable/
RUN helm repo add stackable-test https://repo.stackable.tech/repository/helm-test/
RUN helm repo update

# copy Python sources
COPY src/ /src/

# copy JJB templates
COPY jjb/ /jjb/

# copy catalog
COPY catalog/*.yaml /

ENTRYPOINT [ "python", "/src/jenkins-job-builder.py" ]
