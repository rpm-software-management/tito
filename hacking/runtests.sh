#!/bin/bash

# TODO:
#
# * Add option parsing to change behavior, such as reduce verbosity
# * Add makefile with tasks, such as 'build', 'clean', etc.?
#
#
# Usage:
#
# To run all tests on all supported platforms:
#
#     yum -y install docker-io
#     systemctl start docker.service
#     systemctl enable docker.service
#     usermod -aG docker <your-username>
#
# Log out and log in to refresh your secondary group.
# Then run from the root of the project:
#
#     hacking/runtests.sh
#
# If any test fails, the script exits non-zero.
# To get a zero exit status, all tests must pass
# or be skipped.
#
# The script runs a test harness based on
# docker containers and takes several minutes
# to run on the first build.
# (or if you remove the images)
#
#
# Expected output resembles:
#
#     -snip copious output-
#     =====================
#     Summary
#     /tmp/titotest-centos-5.9-python.out     : OK (SKIP=1)
#     /tmp/titotest-centos-6.4-python.out     : OK (SKIP=1)
#     /tmp/titotest-fedora-20-python.out      : OK
#     /tmp/titotest-fedora-20-python3.out     : OK
#
# You can then review the output, such as:
#
#     $ grep SKIP: /tmp/titotest-*.out
#     /tmp/titotest-centos-5.9-python.out:... SKIP: git-annex is not available in epel-5
#     /tmp/titotest-centos-6.4-python.out:... SKIP: git-annex '3.20120522 ' is too old
#
# After you run the test harness the first time,
# you can optionally enter a container like so:
#
#                  .--- remove container when done (not image)
#                  |
#                  |   .--- interactive
#                  |   |  .--- tty
#                  |   |  |  .---- mount current workdir into container
#                  |   |  |  |                    .---- name of image
#                  |   |  |  |                    |                   .-- get a shell
#                  |   |  |  |                    |                   |
#     docker run --rm -i -t -v $PWD:/home/sandbox titotest-centos-5.9 /bin/bash

distros='
titotest-centos-5.9
titotest-centos-6.4
titotest-fedora-20
'

python3_distros='
titotest-fedora-20
'

rm -f /tmp/titotest*.out &> /dev/null
summary=/tmp/titotest.out

if ! [[ -x runtests.py ]]; then
    echo 'ERROR: must run from root of repo' >&2
    exit 1
fi

header() {
    echo
    echo =====================
    echo $*
}

build_image() {
    name=$1
    header $name
    # Use hard link + gitignore as workaround for
    # https://github.com/dotcloud/docker/issues/1676
    # Do not use...
    #   symlink: not available when building image
    #   cp: invalidates docker build cache
    ln -f tito.spec hacking/$name/
    pushd hacking/$name && echo $PWD && docker build --rm -t $name .
    popd
    rm -f hacking/$name/tito.spec
}

run_inside_image() {
    name=$1
    python_cmd=$2
    outfile=/tmp/${name}-${python_cmd}.out
    header $name

    # --rm                 => remove container after run
    # -i                   => interactive
    # -t                   => tty
    # -v host:container:ro => mount host in container read-only
    docker_run="docker run --rm -i -t -v $PWD:/home/sandbox:ro"
    printf "%-40s: " $outfile >> $summary
    $docker_run $name $python_cmd ./runtests.py -vv 2>&1 | tee $outfile
    tail -1 $outfile >> $summary
}

echo "Building docker images..."
for distro in $distros; do
    build_image $distro || exit 1
done

for distro in $distros; do
    run_inside_image $distro python
done

for distro in $python3_distros; do
    run_inside_image $distro python3
done

header 'Summary'
cat $summary
egrep '\bFAIL' $summary &> /dev/null
[[ $? -eq 0 ]] && exit 1 || exit 0
