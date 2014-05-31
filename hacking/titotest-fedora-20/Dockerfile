# https://index.docker.io/_/fedora/
FROM fedora:20

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# F20 needs updates to resolve conflict with asciidoc.
RUN yum -y update; yum clean all

# NOTE: runtests.sh hard-links tito.spec into this directory on-the-fly
#       to work around https://github.com/dotcloud/docker/issues/1676
ADD tito.spec /tmp/tito.spec

# Install build dependencies.
RUN yum -y install yum-utils \
    ; yum-builddep -y /tmp/tito.spec \
    ; yum clean all

RUN useradd sandbox
RUN git config --global user.email "sandbox@example.com"
RUN git config --global user.name  "sandbox"

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
