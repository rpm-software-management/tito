# https://index.docker.io/_/fedora/
FROM fedora:rawhide

# http://jumanjiman.github.io/
MAINTAINER Paul Morgan <jumanjiman@gmail.com>

# Run an update to work around https://bugzilla.redhat.com/show_bug.cgi?id=1409590
# TODO: remove this once the Rawhide base image is updated
RUN dnf -y update
# Install build dependencies including python2 deps for testing.
RUN dnf -y install          \
    'dnf-command(builddep)' \
    git-annex               \
    python3-devel           \
    python3-mock            \
    python3-nose            \
    python3-blessed         \
    python3-pycodestyle     \
    rsync                   \
    createrepo_c

RUN useradd sandbox
RUN git config --system user.email "sandbox@example.com"
RUN git config --system user.name  "sandbox"

# NOTE: runtests.sh hard-links tito.spec into this directory on-the-fly
#       to work around https://github.com/dotcloud/docker/issues/1676
ADD tito.spec /tmp/tito.spec

RUN dnf -y builddep /tmp/tito.spec
RUN dnf clean all

USER sandbox
VOLUME ["/home/sandbox"]
WORKDIR /home/sandbox

ENV LANG C
CMD ["/bin/bash"]
