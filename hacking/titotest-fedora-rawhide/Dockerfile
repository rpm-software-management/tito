# https://index.docker.io/_/fedora/
FROM fedora:rawhide

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# NOTE: runtests.sh hard-links tito.spec into this directory on-the-fly
#       to work around https://github.com/dotcloud/docker/issues/1676
ADD tito.spec /tmp/tito.spec

# Install build dependencies.
RUN yum -y install \
    yum-utils \
    git-annex \
    python-mock \
    python-nose \
    python-pep8

RUN yum -y install \
    python3-mock \
    python3-nose \
    python3-pep8

RUN yum-builddep -y /tmp/tito.spec
RUN yum clean all
#RUN yum -y install yum-utils \
#    ; yum-builddep -y /tmp/tito.spec \
#    ; yum clean all

RUN yum install -y python-devel

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
