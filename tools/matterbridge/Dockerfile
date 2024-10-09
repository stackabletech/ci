FROM ubuntu:latest
LABEL maintainer="Stackable GmbH"

WORKDIR /app
RUN apt-get update && apt-get upgrade -y && apt-get install -y curl && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN curl -LO https://github.com/42wim/matterbridge/releases/download/v1.26.0/matterbridge-1.26.0-linux-64bit
ADD matterbridge-1.26.0-linux-64bit.sha256 /app/matterbridge-1.26.0-linux-64bit.sha256
RUN sha256sum -c matterbridge-1.26.0-linux-64bit.sha256
RUN chmod +x matterbridge-1.26.0-linux-64bit

ENTRYPOINT ["/app/matterbridge-1.26.0-linux-64bit", "-conf", "/app/conf/matterbridge.toml"]
