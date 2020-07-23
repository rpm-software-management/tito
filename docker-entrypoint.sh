#!/bin/bash

# Find executables
DNF="sudo $(which dnf)"
GIT=$(which git)
TITO=$(which tito)

# Parse args
[ $# -lt 1 ] && { echo "USAGE: $(basename ${BASH_SOURCE[0]}) <TITO_COMMAND> [ARGS..]" >&2; exit 1; }

TITO_COMMAND=$1; shift

# Set permissions
sudo chown -R builder:builder /workspace

# Parse env
echo "Parse env vars"
git_username="${GIT_USERNAME:-user}"
git_email="${GIT_EMAIL:-user@example.com}"

echo "Setup git config"
${GIT} config --global user.name  "${git_username}"
${GIT} config --global user.email "${git_email}"

# If /workspace is empty, clone GIT_URL inside, or fail if not set.
if ! [ "$(ls -A /workspace)" ]; then
    if [ -z "${GIT_URL}" ]; then
        echo "error: /workspace is empty and GIT_URL not provided." >&2
        exit 2
    fi
    ${GIT} clone "${GIT_URL}" /workspace
fi

if [ "${TITO_COMMAND}" = "build" ]; then
    spec="$(find . -maxdepth 1 -type f -name '*.spec' | head -n1)"
    if [ -z "${spec}" ]; then
        echo "error: could not find spec file." >&2
        exit 2
    fi
    echo "installing build dependencies"
    ${DNF} -y builddep --spec "${spec}"
fi

# Main
${TITO} "${TITO_COMMAND}" "$@"
