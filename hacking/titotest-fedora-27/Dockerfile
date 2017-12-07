FROM fedora:27
MAINTAINER Steve Kuznetsov <skuznets@redhat.com>

# Manually install python2 deps since spec won't add them
RUN dnf -y install                 \
           'dnf-command(builddep)' \
           git-annex               \
           python2-devel           \
           python-mock             \
           python-nose             \
           python-blessings        \
           python-pep8             \
           python-setuptools       \
           python-bugzilla         \
           python2-rpm             \
           python3-mock            \
           python3-nose            \
           python3-blessings       \
           python3-pep8            \
	   rsync                   \
           createrepo_c

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"
ADD tito.spec /tmp/tito.spec
RUN dnf -y builddep /tmp/tito.spec
RUN dnf clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
