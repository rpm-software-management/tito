#!/usr/bin/perl
#
# Copyright (c) 2008-2009 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.


use strict;
use warnings FATAL => 'all';

my $command = shift @ARGV;
if (not defined $command
	or ($command ne 'bump-version' and $command ne 'bump-release' and $command ne 'zstream-release')) {
	usage();
}
my $specfile = 0;
if (@ARGV and $ARGV[0] eq '--specfile') {
	$specfile = 1;
	shift @ARGV;
}
if (not @ARGV) {
	usage();
}

sub usage {
	die "usage: $0 { bump-version | bump-release | zstream-release } [--specfile] file [ files ... ]\n";
}

my $newfile;
my @content;
while (<ARGV>) {
	if ($specfile) {
		if ($command eq 'bump-version') {
			s/^(version:\s*)(.+)/ $1 . bump_version($2) /ei;
			s/^(release:\s*)(.+)/ $1 . reset_release($2) /ei;
		} elsif ($command eq 'bump-bump-release') {
			s/^(release:\s*)(.+)/ $1 . bump_version($2) /ei;
		} else { # zstream-release Release: 7%{?dist}
			s/^(release:\s*)(.+)/ $1 . bump_zstream($2) /ei;
		}
		push @content, $_;
	} else {
		chomp;
		my ($version, $release, $rest) = split /\s/, $_, 3;
		if ($command eq 'bump-version') {
			$version = bump_version($version);
			$release = reset_release($release);
		} else {
			$release = bump_version($release);
		}
		if (defined $rest) {
			$release .= ' ' . $rest;
		}
		push @content, "$version $release\n";
		# slurp the rest of the file
		while (not eof(ARGV)) {
			push @content, scalar <ARGV>;
		}
	}

} continue {
	if (eof(ARGV)) {
		local *OUT;
		undef $newfile;
		if ($ARGV eq '-') {
			*OUT = \*STDOUT;
		} else {
			$newfile = $ARGV . ".$$";
			open OUT, "> $newfile" or die "Error writing [$newfile]: $!\n";
		} 
		print OUT @content;
		if (defined $newfile) {
			close OUT;
			rename $newfile, $ARGV;
		}
	}
}

sub bump_version {
	local $_ = shift;
	no warnings 'uninitialized';
	s/^(.+\.)?([0-9]+)(\.|%|$)/$1 . ($2 + 1) . $3/e;
	$_;
}

sub bump_zstream {
    my $version = shift;
    # if we do not have zstream, create .0 and then bump the version
    $version =~ s/^(.*)(%{\?dist})$/$1$2.0/i;
    return bump_version($version);
}

sub reset_release {
	local $_ = shift;
	s/(^|\.)([.0-9]+)(\.|%|$)/${1}1$3/;
	$_;
}

__END__ {
	if (defined $newfile and -f $newfile) {
		unlink $newfile;
	}
}

1;

