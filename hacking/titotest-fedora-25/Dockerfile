FROM fedora:25
MAINTAINER Steve Kuznetsov <skuznets@redhat.com>

RUN dnf -y install           \
           yum-utils         \
           git-annex         \
           python2           \
           python-devel      \
           python-mock       \
           python-nose       \
           python-blessings  \
           python-pep8       \
           python3-mock      \
           python3-nose      \
           python3-blessings \
           python3-pep8

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"
ADD tito.spec /tmp/tito.spec
RUN yum-builddep -y /tmp/tito.spec
RUN dnf clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
