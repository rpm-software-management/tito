# https://index.docker.io/_/centos/
FROM tianon/centos:6.4

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# Install dependencies.
RUN yum -y install git rpm-build python-devel python-nose \
    libxslt asciidoc python-setuptools tar createrepo which
RUN rpm -Uvh http://ftp.linux.ncsu.edu/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm
RUN yum -y install python-pep8 git-annex python-mock

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
