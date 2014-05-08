# https://index.docker.io/_/centos/
FROM tianon/centos:5.9

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# Install dependencies.
RUN rpm -Uvh http://mirror.es.its.nyu.edu/epel/5/x86_64/epel-release-5-4.noarch.rpm
RUN yum -y install git rpm-build \
    python-devel python-nose python-setuptools python-pep8 \
    python-pip \
    libxslt asciidoc tar createrepo which

RUN pip-python install mock --upgrade

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
