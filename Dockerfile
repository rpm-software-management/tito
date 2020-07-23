ARG CENTOS_VERSION="8.2.2004"
FROM centos:${CENTOS_VERSION}

# This is used in the entrypoint to set
# the builder git config
ENV GIT_USERNAME "user"
ENV GIT_EMAIL    "user@example.com"

# Update cache and install tito dependencies,
# as well as the 'Development Tools' package group
RUN dnf clean all \
 && dnf -y --setopt="tsflags=nodocs" update \
 && dnf -y --setopt="tsflags=nodocs" install \
    which \
    sudo \
    git \
    rpm-build \
    redhat-rpm-config \
    rpmdevtools \
    python36 \
    maven \
 && dnf -y --setopt="tsflags=nodocs" group install "Development Tools" \
 && dnf clean all \
 && rm -rf /var/cache/dnf

# Install tito from github
# TODO: add ARG to select version to pull
RUN mkdir -p /usr/local/lib/python3.6/site-packages \
 && git clone https://github.com/rpm-software-management/tito.git /tmp/tito-package \
 && cd /tmp/tito-package \
 && pip3 install .

# Create builder user and setup environment
ARG GIT_DOMAIN=github.com
RUN useradd builder -u 1000 -m -G users,wheel \
 && echo "builder ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers \
 && mkdir /workspace \
 && chown builder:builder /workspace \
 && mkdir -m 700 -p /home/builder/.ssh \
 && ssh-keyscan -t rsa "${GIT_DOMAIN}" >> /home/builder/.ssh/known_hosts \
 && chown -R builder:builder /home/builder/.ssh

# Switch to builder
USER builder

# Expose the workspace as a volume to let
# users map a local repository inside the container
VOLUME /workspace

WORKDIR /workspace

# To build packages without needing to have local repositories,
# set the GIT_URL environment variable to let
# the entrypoint clone the repository.
COPY --chown=builder:builder ./docker-entrypoint.sh /
RUN chmod 755 /docker-entrypoint.sh

# The entrypoint will install build dependencies using
# dnf builddep when run using "build" command.
ENTRYPOINT ["/docker-entrypoint.sh"]
