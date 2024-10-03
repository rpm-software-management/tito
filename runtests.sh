#! /bin/bash -e
cov=--cov
args=()
for arg; do
case $arg in
--no-cov) cov= ;;
*) args+=( "$arg" )
esac
done
exec python3 -m pytest -vv $cov "${args[@]}"
