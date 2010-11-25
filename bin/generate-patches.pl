#!/usr/bin/perl

use strict;
use warnings FATAL => 'all';

use Getopt::Long ();
use IPC::Open3 ();

my $target_directory;

sub usage {
	die "Usage: $0 -d target_directory package_name start_version_release end_version_release [commit_id]\n";
}

sub check_git_tag {
	my $tag = join_tag_parts(@_);
	my ($wtr, $rdr);

	my $pid = IPC::Open3::open3($wtr, $rdr, undef, 'git', 'tag', '-l', $tag);
	close($wtr);
	my $check = <$rdr>;
	close($rdr);
	if (waitpid($pid, 0) < 0) {
		die "Error checking for tag [$tag], process died: $!\n";
	}
	if (not defined $check) {
		return;
	}
	chomp $check;
	if ($check eq $tag) {
		return 1;
	}
	return;
}

sub split_version_to_parts {
	my $version = shift;
	my @parts1 = split /-/, $version;
	my @parts2;
	for my $p (@parts1) {
		push @parts2, [ split /\./, $p ];
	}
	return @parts2;
}

sub join_tag_parts {
	my @parts = @_;
	for my $p (@parts) {
		if (ref $p) {
			$p = join '.', @$p;
		}
	}
	return join '-', @parts;
}

if (not Getopt::Long::GetOptions('dir=s' => \$target_directory)) {
	usage();
}

if (not defined $target_directory) {
	usage();
}

my ($package, $start_version, $end_version, $commit_id) = @ARGV;

if (not defined $end_version) {
	usage();
}

if (not -d $target_directory) {
	die "The target directory [$target_directory] does not exist.\n";
}

if (not check_git_tag($package, $start_version)) {
	die "Start tag [$package-$start_version] does not exist.\n";
}
if (not check_git_tag($package, $end_version)) {
	die "End tag [$package-$end_version] does not exist.\n";
}

my @start_version = split_version_to_parts($start_version);
my @end_version = split_version_to_parts($end_version);

if (@start_version != 2) {
	die "Start version needs to have two segments (version-release).\n";
}
if ("@{$start_version[1]}" ne "1") {
	die "The start second segment (release) has to be 1.\n";
}
if (@end_version < @start_version) {
	die "End version needs to have the same or more segments than the start version..\n";
}
if ("@{$start_version[0]}" ne "@{$end_version[0]}") {
	die "The first segment (version) has to match.\n";
}

my @path;

unshift @path, join_tag_parts($package, @end_version);
while ("@{$end_version[1]}" ne "1") {
	my @release = @{$end_version[1]};
	if ($release[-1] eq '0') {
		splice @release, $#release;
	} elsif ($release[-1] =~ /^[0-9]+$/) {
		$release[-1] -= 1;
	} else {
		# drop non-numerical segment
		splice @release, $#release;
	}
	$end_version[1] = \@release;
	my $tag = join_tag_parts($package, @end_version);
	if (check_git_tag($tag)) {
		unshift @path, $tag;
	}
}

while (@end_version > @start_version) {
	splice @end_version, $#end_version;
	my $tag = join_tag_parts($package, @end_version);
	if (check_git_tag($tag)) {
		unshift @path, $tag;
	}
}

for (my $i = 0; $i < @path - 1; $i++) {
	my $patch_name = "$path[$i]-to-$path[$i + 1].patch";
	system "git diff --relative $path[$i]..$path[$i + 1] > $target_directory/$patch_name";
	print "$patch_name\n";
}

if (defined $commit_id) {
	my $patch_name = "$path[$#path]-to-$package-git-$commit_id.patch";
	system "git diff --relative $path[$#path]..$commit_id > $target_directory/$patch_name";
	if (-s "$target_directory/$patch_name") {
		print "$patch_name\n";
	} else {
		unlink "$target_directory/$patch_name";
	}
}
