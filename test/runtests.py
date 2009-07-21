#!/usr/bin/env python

import sys
import os
import os.path

# Python libraries are one level up from where this script lives:
TEST_SCRIPT_DIR = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(TEST_SCRIPT_DIR, "../src/"))

import spacewalk.releng.cli # prevents a circular import
from spacewalk.releng.common import *

# A location where we can safely create a test git repository.
# WARNING: This location will be destroyed if present.
TEST_GIT_LOCATION = '/tmp/tito-test-git-repo'

if __name__ == '__main__':
    print "Running tito tests."

    if os.path.exists(TEST_GIT_LOCATION):
        #error_out("Test Git repo already exists: %s" % TEST_GIT_LOCATION)
        run_command('rm -rf %s' % TEST_GIT_LOCATION)

    run_command('mkdir -p %s' % TEST_GIT_LOCATION)
    run_command('cp -R %s/* %s' % (os.path.join(TEST_SCRIPT_DIR,
        'fakegitfiles'), TEST_GIT_LOCATION))
    os.chdir(TEST_GIT_LOCATION)
    run_command('git init')
    run_command('git add a.txt')
    run_command('git commit -a -m "added a.txt"')
    run_command('git add b.txt')
    run_command('git commit -a -m "added b.txt"')
    run_command('git add c.txt')
    run_command('git commit -a -m "added c.txt"')


