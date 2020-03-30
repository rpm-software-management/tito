Hacking
=======

This is the developer documentation for
https://github.com/rpm-software-management/tito

Python versions
---------------

Tito supports Python versions 2.4 (RHEL 5) and up.
See http://docs.python.org/dev/howto/pyporting.html
and http://python3porting.com/differences.html
and https://docs.python.org/3.0/whatsnew/3.0.html
for tips on writing portable Python code.

In particular, you must capture exceptions in a way that's
compatible with both python 2.4 and 3.x. For example:

    try:
        raise Exception()
    except Exception:
        import sys
        exc = sys.exc_info()[1]
        # Current exception is 'exc'.
        pass


Tests
-----

### Docker test harness

To run all tests on all supported platforms:

    yum -y install docker
    systemctl enable --now docker.service
    usermod -aG docker <your-username>

Log out and log in to refresh your secondary group.
Then run from the root of the project:

    hacking/runtests.sh

If any test fails, the script exits non-zero.
To get a zero exit status, all tests must pass
or be skipped.

The above script runs a test harness based on
docker containers and takes several minutes to run
on the first build (or if you remove the images).

Expected output resembles:

    -snip copious output-
    =====================
    Summary
    /tmp/titotest-centos-6-python.out     : OK (SKIP=1)
    /tmp/titotest-fedora-25-python3.out     : OK

You can then review the output, such as:

    $ grep SKIP: /tmp/titotest-*.out
    /tmp/titotest-centos-6-python.out:... SKIP: git-annex '3.20120522 ' is too old

After you run the test harness the first time,
you can optionally create and enter a container like so:

                 .--- remove container when done (not image)
                 |
                 |   .--- interactive
                 |   |  .--- tty
                 |   |  |  .---- mount current workdir into container
                 |   |  |  |                    .---- name of image
                 |   |  |  |                    |                 .-- get a shell
                 |   |  |  |                    |                 |
    docker run --rm -i -t -v $PWD:/home/sandbox titotest-centos-6 /bin/bash


Note about the sandbox: By default, the docker container is a
read-only execution environment to protect your source from changes.
If you are comfortable with LXC, you can override it to provide
an authoring environment, too.


### Workstation tests

To run all tests, install these packages:

* python-nose,  python-pep8,  python-mock (for epl-6 and fedora) and rpm-python
* python3-nose, python3-pep8,  python3-mock (for epl-6 and fedora) , and rpm-python3
* createrepo_c
* git-annex

For epel-5:
There is also a need to install additional library via pip (pip install mock)
for python 2.4 - 2.7 (in case you don't have pip, install via yum python-pip package)
* mock

Then from the root of the project:

    python  ./runtests.py -vv
    python3 ./runtests.py -vv


### Advanced

When developing code for tito there are a couple ways you can test:

First install Tito's dependencies for your architecture, i.e. `x86_64`, like
described in [README's INSTALL section](README.md#INSTALL), under installation
from git's `master` branch.

Then create a virtual environment and install tito in editable mode:

    python3 -m venv --system-site-packages tito-venv
    source tito-venv/bin/activate
    pip install -e .

And of course, you can always use the installed tito to replace
itself with a test build of the latest *committed* code in your
git HEAD.

    tito build --rpm --test -i

If you screw anything up inside tito itself, you can just:

    rpm -e tito
    yum install tito


Code style
----------

Python3 does not allow mixing tabs and spaces for indentation.
http://docs.python.org/3.3/reference/lexical_analysis.html

You can force your editor to do the right thing by installing
a plugin for your editor from http://editorconfig.org/#download

For example, add the EditorConfig plugin for vim like this:

    cd /tmp/
    wget https://github.com/editorconfig/editorconfig-vim/archive/master.zip
    unzip master.zip
    mkdir ~/.vim
    cp -r editorconfig-vim-master/* ~/.vim/
