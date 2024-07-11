FROM python:3

# install required Python modules
COPY python_modules /
RUN pip install --no-cache-dir -r python_modules

# install Replicated CLI
RUN mkdir -p /tmp/replicated/
RUN curl "https://raw.githubusercontent.com/replicatedhq/replicated/master/install.sh" > /tmp/replicated/install.sh
RUN chmod a+x /tmp/replicated/install.sh
RUN /tmp/replicated/install.sh

# install kubectl
RUN wget -O /tmp/kubectl "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
RUN install -o root -g root -m 0755 /tmp/kubectl /usr/local/bin/kubectl
RUN rm /tmp/kubectl

# install Helm and the Stackable Helm repos
RUN curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -s -
RUN helm repo add stackable-dev https://repo.stackable.tech/repository/helm-dev/
RUN helm repo add stackable-stable https://repo.stackable.tech/repository/helm-stable/
RUN helm repo add stackable-test https://repo.stackable.tech/repository/helm-test/
RUN helm repo update

# install beku
RUN pip install beku-stackabletech

# install stackablectl
RUN curl -L https://github.com/stackabletech/stackable-cockpit/releases/latest/download/stackablectl-x86_64-unknown-linux-gnu --output /usr/local/bin/stackablectl 
RUN chmod a+x /usr/local/bin/stackablectl 

# install kubectl-kuttl
RUN wget -O /tmp/kubectl-kuttl https://github.com/kudobuilder/kuttl/releases/download/v0.11.1/kubectl-kuttl_0.11.1_linux_x86_64
RUN install -o root -g root -m 0755 /tmp/kubectl-kuttl /usr/local/bin/kubectl-kuttl
RUN rm /tmp/kubectl-kuttl

# Install tools used by tests

# Mike Farah's yq
RUN curl --fail -L https://github.com/mikefarah/yq/releases/download/v4.44.2/yq_linux_amd64.tar.gz | tar -C /tmp -xzf - && \
  mv /tmp/yq_linux_amd64 /usr/local/bin/yq && \
  chmod +x /usr/local/bin/yq

# - gettext-base provides envsubst
RUN apt update && \
    apt install -y \
       jq \
       gettext-base && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# copy main Python script
COPY *.py /

# copy config file
COPY replicated.yaml /

ENTRYPOINT [ "python", "/replicated-testrunner.py" ]
