# https://index.docker.io/_/centos/
FROM mattdm/fedora:f20

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# F20 needs updates to resolve conflict with asciidoc.
RUN yum -y update; yum clean all

# Install dependencies.
RUN yum -y install git rpm-build libxslt tar \
    asciidoc \
    python-devel python-nose python-setuptools python-pep8 \
    python-mock \
    python3-devel python3-nose python3-setuptools python3-pep8 rpm-python3 python3-mock \
    createrepo git-annex which python-bugzilla python3-bugzilla

# Remove yum metadata.
RUN yum clean all

RUN useradd sandbox
RUN git config --global user.email "sandbox@example.com"
RUN git config --global user.name  "sandbox"

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
