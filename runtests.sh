#! /bin/bash -e
cov=--cov
args=()
for arg; do
case $arg in
--no-cov) cov= ;;
*) args+=( "$arg" )
esac
done
PYTHONPATH=$PWD/src exec python3 -m pytest -vv $cov "${args[@]}"
