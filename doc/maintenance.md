# Maintenance documentation

## Release process

If you are releasing a new version of Tito, please follow these steps:

1. Make sure Travis tests are passing
2. Make sure it is possible to build tito package from `master` branch for all
   currently supported Fedora versions. Either by using [mock][mock], or using
   Copr `tito release copr --test`
3. Make sure that `[fedora]` releaser in `.tito/releasers.conf` contains all
   currently supported Fedora and Epel branches.
4. Tag a new version `tito tag --use-version=` (drop the .postX suffix) and
   follow its instructions
5. Go to the [GitHub releases page][releases] and
   - write a propper release notes
   - upload source tarball that you generate with `tito build --tgz`
6. Push new version into Fedora DistGit and build it in Koji
   `tito release fedora`
7. Make sure those builds succeeds and submit updates into Bodhi
8. Release into PyPI with `python3 setup.py sdist` and `twine upload
   dist/<NAME-VERSION>.tar.gz`
9. Manually bump tito.spec Version to `<version>.post1` (in a separate commit)
   to make sure that the ENVRA from the main branch beats the one from distro.



[mock]: https://github.com/rpm-software-management/mock
[releases]: https://github.com/dgoodwin/tito/releases
