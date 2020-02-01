# https://index.docker.io/_/centos/
FROM centos:6

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# Install test dependencies. It would be nice to add these as
# build deps and add %check to tito.spec in accordance with
# https://fedoraproject.org/wiki/QA/Testing_in_check
# but some of the packages come from EPEL.
RUN rpm -Uvh http://ftp.linux.ncsu.edu/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm
RUN rpm -Uvh http://download-ib01.fedoraproject.org/pub/epel/6/x86_64/Packages/p/python-unittest2-0.5.1-3.el6.noarch.rpm
RUN yum -y install \
    git \
    git-annex \
    python-bugzilla \
    python-mock \
    python-nose \
    python-pep8 \
    rpm-build \
    createrepo_c \
    tar \
    python-devel \
    which \
    asciidoc \
    docbook-style-xsl \
    libxslt \
    rpmdevtools \
    python-blessed \
    ; yum clean all

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"

# NOTE: runtests.sh hard-links tito.spec into this directory on-the-fly
#       to work around https://github.com/dotcloud/docker/issues/1676
ADD tito.spec /tmp/tito.spec

# Install build dependencies.
RUN yum -y install yum-utils \
    ; yum-builddep -y /tmp/tito.spec \
    ; yum clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox


ENV LANG C
CMD ["/bin/bash"]
