# Copyright (c) 2015 John Florian <jflorian@doubledog.org>
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.


__tito_modules='build init release report tag'

# Excluding short options here because they'd save no keystrokes and only make
# these longer, more intuitive options less accessible.
__tito_opts='--help'

__tito_build_opts='
    --arg=
    --builder=
    --debug
    --dist=
    --help
    --install
    --list-tags
    --no-cleanup
    --output=
    --rpm
    --rpmbuild-options=
    --scl=
    --srpm
    --tag=
    --test
    --tgz
    --verbose
    --fetch-sources
'

__tito_release_opts='
    --all
    --all-starting-with=
    --debug
    --dry-run
    --help
    --list
    --no-build
    --no-cleanup
    --output=
    --scratch
    --tag=
    --test
    --yes
'

__tito_report_opts='
    --debug
    --help
    --output=
    --untagged-diffs
    --untagged-commits
'

__tito_tag_opts='
    --accept-auto-changelog
    --auto-changelog-message=
    --changelog
    --debug
    --help
    --keep-version
    --no-auto-changelog
    --output=
    --undo
    --use-version=
'

_tito_get_release_targets() {
    # Ideally tito would return an exit code of 0 upon success, but it seems
    # to return 1 whether run within a git checkout or not.  Hence this
    # kludge:
    if tito release --list 2> /dev/null | grep -q 'Available release targets'
    then
        tito release --list | tail -n +2
    fi
}

_tito() {
    local cur opts module

    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    module="${COMP_WORDS[1]}"

    opts="${__tito_modules} ${__tito_opts}"

    case "${module}" in

        build)
            COMPREPLY=( $(compgen -W "${__tito_build_opts}" -- ${cur}) )
            return 0
            ;;

        release)
            COMPREPLY=( $(compgen -W \
                        "${__tito_release_opts} $(_tito_get_release_targets)" \
                        -- ${cur}) \
                      )
            return 0
            ;;

        report)
            COMPREPLY=( $(compgen -W "${__tito_report_opts}" -- ${cur}) )
            return 0
            ;;

        tag)
            COMPREPLY=( $(compgen -W "${__tito_tag_opts}" -- ${cur}) )
            return 0
            ;;

    esac

    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}

complete -F _tito tito
