FROM centos:7
MAINTAINER Steve Kuznetsov <skuznets@redhat.com>

RUN yum -y install epel-release
RUN yum -y install           \
           git               \
           git-annex         \
           python-bugzilla   \
           python-mock       \
           python-nose       \
           python-pep8       \
           rpm-build         \
           createrepo_c      \
           tar               \
           python-devel      \
           which             \
           asciidoc          \
           docbook-style-xsl \
           libxslt           \
           rpmdevtools       \
           python-blessed    \
    && yum clean all

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"
ADD tito.spec /tmp/tito.spec
RUN yum -y install yum-utils \
    && yum-builddep -y /tmp/tito.spec \
    && yum clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox


ENV LANG C
CMD ["/bin/bash"]
