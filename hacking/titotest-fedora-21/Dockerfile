# https://index.docker.io/_/fedora/
FROM fedora:21

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# Install build dependencies.
RUN yum -y install \
    yum-utils \
    git-annex \
    python-devel \
    python-mock \
    python-nose \
    python-blessings \
    python-pep8 \
    python3-mock \
    python3-nose \
    python3-blessings \
    python3-pep8

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"

# NOTE: runtests.sh hard-links tito.spec into this directory on-the-fly
#       to work around https://github.com/dotcloud/docker/issues/1676
ADD tito.spec /tmp/tito.spec

RUN yum-builddep -y /tmp/tito.spec
RUN yum clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
