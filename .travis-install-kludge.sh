#!/bin/bash

# GitPython does not currently support python3 and
# may be replaced by pygit2.
# https://fedoraproject.org/wiki/User:Churchyard/python3
if [[ $(python --version 2>&1) =~ ^2 ]]; then
  pip install 'GitPython >= 0.2.0' --use-mirrors --pre
fi
