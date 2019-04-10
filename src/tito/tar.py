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

import re
import struct
import sys
import codecs
import tito.compat

RECORD_SIZE = 512

# Git writes its tarballs to be a multiple of 10240.  I'm not sure why: the
# implementation in archive-tar.c doesn't have any comments on the matter.
GIT_BLOCK_SIZE = RECORD_SIZE * 20


class TarFixer(object):
    """Code for updating a tar header's mtime.  For details on the tar format
    see http://www.gnu.org/software/tar/manual/html_node/Standard.html and
    http://en.wikipedia.org/wiki/Tar_%28computing%29

    Tito passes "git archive" a tree ID.  The "git archive" man page states:

        git archive behaves differently when given a tree ID versus when given
        a commit ID or tag ID. In the first case the current time is used as
        the modification time of each file in the archive.

    Using the current time means that every time we build the source tarball,
    the file fingerprint will change since the metadata in the tarball changes.
    We don't want that since build systems track the fingerprint to see if
    the actual source has changed.

    The resultant tarball will be in this format:

        - Global header (512 bytes)
        - Extended header block with git ref (512 bytes)
        - [File header (512 bytes) + File data padded to multiple of 512] * number of files
        - 1024 NUL bytes
        - However many NUL bytes are necessary to pad the file to a multiple of GIT_BLOCK_SIZE

    The block after the global header with the git ref is called an "extended header".
    We are technically writing a "pax" archive because of the use of extensions.  According
    to the comments in git's archive-tar.c

        pax extended header records have the format "%u %s=%s\n".  %u contains
        the size of the whole string (including the %u), the first %s is the
        keyword, the second one is the value.

    PAX (also known as POSIX.1-2001) always encodes everything in UTF-8.
    """
    def __init__(self, fh, out, timestamp, gitref, maven_built=False):
        self.maven_built = maven_built

        # As defined in tar.h
        # An collections.OrderedDict would be more appropriate here but I'm trying to
        # maintain Python 2.6 compatibility.
        self.tar_struct = [
            ('name', '100s'),
            ('mode', '8s'),
            ('uid', '8s'),
            ('gid', '8s'),
            ('size', '12s'),
            ('mtime', '12s'),
            ('checksum', '8s'),
            ('typeflag', '1s'),
            ('linkname', '100s'),
            ('magic', '6s'),
            ('version', '2s'),
            ('uname', '32s'),
            ('gname', '32s'),
            ('devmajor', '8s'),
            ('devminor', '8s'),
            ('prefix', '155s'),
        ]

        # The items in the list below are zero-padded octal numbers in ASCII.
        # All other fields are null-terminated character strings. Each numeric
        # field of width w contains w minus 1 digits, and a null.
        #
        # The checksum is technically an octal_member but we handle it specially.
        self.octal_members = [
            'mode',
            'uid',
            'gid',
            'size',
            'mtime',
            'devmajor',
            'devminor',
        ]

        # Add an '=' to use native byte order with standard sizes
        self.struct_template = "=" + "".join(map(lambda x: x[1], self.tar_struct))
        self.struct_members = list(map(lambda x: x[0], self.tar_struct))
        self.struct_hash = dict(self.tar_struct)

        # The tarballs created by git archive from tree IDs don't have a global
        # header for some reason.
        self.need_header = True
        self.done = False

        # We need to track the total number of bytes we've written so we can
        # pad out the final tarball to be a multiple of GIT_BLOCK_SIZE
        self.total_length = 0

        self.fh = fh
        self.out = out
        self.timestamp = int(timestamp)
        self.gitref = gitref

    def full_read(self, read_size):
        read = self.fh.read(read_size)
        amount_read = len(read)
        while amount_read < read_size:
            left_to_read = read_size - amount_read
            next_read = self.fh.read(left_to_read)

            if next_read == '':
                raise IOError("Buffer underflow when reading")

            amount_read += len(next_read)
            read = read + next_read

        return read

    def write(self, data):
        self.out.write(tito.compat.ensure_binary(data))

    def chunk_to_hash(self, chunk):
        # Our struct template is only 500 bytes, but the last 12 bytes are NUL
        # I elected to ignore them completely instead of including them in the
        # template as '12x'.  The unpack_from method will read the bytes our
        # template defines from chunk and discard the rest.
        unpacked = struct.unpack_from(self.struct_template, chunk)
        unpacked = list(map(lambda x: tito.compat.ensure_text(x), unpacked))
        # Zip what we read together with the member names and create a dictionary
        chunk_props = dict(zip(self.struct_members, unpacked))

        return chunk_props

    def padded_size(self, length, pad_size=RECORD_SIZE):
        """Function to pad out a length to the nearest multiple of pad_size
        that can contain it."""
        blocks = length // pad_size
        if length % pad_size != 0:
            blocks += 1
        return blocks * pad_size

    def create_global_header(self):
        header_props = {
            'name': u'pax_global_header',
            'mode': 0o666,
            'uid': 0,
            'gid': 0,
            'size': 52,  # The size of the extended header with the gitref
            'mtime': self.timestamp,
            'typeflag': u'g',
            'linkname': u'',
            'magic': u'ustar',
            'version': u'00',
            'uname': u'root',
            'gname': u'root',
            'devmajor': 0,
            'devminor': 0,
            'prefix': u'',
        }
        self.process_header(header_props)

    def encode_header(self, chunk_props, encode_order=None):
        pack_values = []
        if encode_order is None:
            encode_order = self.struct_members

        for member in encode_order:
            if member in self.octal_members:
                # Pad out the octal value to the right length
                member_template = self.struct_hash[member]
                field_size = int(re.match('(\d+)', member_template).group(1)) - 1
                fmt = "%0" + str(field_size) + "o\x00"
                as_string = fmt % chunk_props[member]
                pack_values.append(tito.compat.ensure_binary(as_string))
            else:
                pack_values.append(tito.compat.ensure_binary(chunk_props[member]))
        return pack_values

    def process_header(self, chunk_props):
        """There is a header before every file and a global header at the top."""
        chunk_props['checksum'] = self.calculate_checksum(chunk_props)
        pack_values = self.encode_header(chunk_props)

        # The struct itself is only 500 bytes so we have to pad it to 512
        data_out = struct.pack(self.struct_template + "12x", *pack_values)
        self.write(data_out)
        self.total_length += len(data_out)

    def process_extended_header(self):
        # Trash the original comment
        self.full_read(RECORD_SIZE)
        self.create_extended_header()

    def create_extended_header(self):
        # pax extended header records have the format "%u %s=%s\n".  %u contains
        # the size of the whole string (including the %u), the first %s is the
        # keyword, the second one is the value.
        #
        # Since the git ref is always 40 ASCII characters we can pre-compute the length
        # to put in the extended header
        comment = "52 comment=%s\n" % self.gitref
        data_out = struct.pack("=52s460x", tito.compat.ensure_binary(comment, "ascii"))
        self.write(data_out)
        self.total_length += len(data_out)

    def process_file_data(self, size):
        data_out = self.full_read(self.padded_size(size))
        self.write(data_out)
        self.total_length += len(data_out)

    def calculate_checksum(self, chunk_props):
        """The checksum field is the ASCII representation of the octal value of the simple
        sum of all bytes in the header block. Each 8-bit byte in the header is added
        to an unsigned integer, initialized to zero, the precision of which shall be
        no less than seventeen bits. When calculating the checksum, the checksum field is
        treated as if it were all spaces.
        """
        chunk_props['checksum'] = " " * 8
        values = self.encode_header(chunk_props)
        new_chksum = 0
        for val in values:
            val_bytes = bytearray(tito.compat.ensure_binary(val))
            for b in val_bytes:
                new_chksum += b
        return "%07o\x00" % new_chksum

    def process_chunk(self, chunk):
        # Tar archives end with two 512 byte blocks of zeroes
        if chunk == b"\x00" * 512:
            self.write(b"\x00" * 512)
            self.total_length += len(chunk)
            if self.last_chunk_was_nulls:
                final_padding = b"\x00" * (self.padded_size(self.total_length, GIT_BLOCK_SIZE) - self.total_length)
                self.write(final_padding)
                self.done = True
            self.last_chunk_was_nulls = True
            return

        self.last_chunk_was_nulls = False

        chunk_props = self.chunk_to_hash(chunk)

        # Delete the old checksum since it's now invalid and we don't want even
        # an inadvertent reference to it.
        del(chunk_props['checksum'])

        # Remove the trailing NUL byte(s) on the end of members
        for k, v in chunk_props.items():
            chunk_props[k] = v.rstrip("\x00")

        # This line is the whole purpose of this class!
        chunk_props['mtime'] = "%o" % self.timestamp

        if self.maven_built:
            # Maven does all sorts of horrible things in the tarfile it creates.
            # Everything is padded out with spaces instead of NUL bytes and the uid
            # and gid fields are left empty.
            #
            # Plus it sets the uname and gname to the current user resulting in
            # the checksum changing from person to person.
            # See https://jira.codehaus.org/browse/PLXCOMP-233
            chunk_props['uname'] = 'root'
            chunk_props['gname'] = 'root'
            chunk_props['uid'] = '0'
            chunk_props['gid'] = '0'
            # In a tar file, the highest 3 bits in the mode represent if the tarfile
            # should be extracted with the GID or UID set.  Maven adds these but we don't
            # want them, so we just take the last 4 which are the ones that matter to us.
            chunk_props['mode'] = str(chunk_props['mode'])[-4:-1]
            chunk_props['version'] = '00'
            for x in ['size', 'devmajor', 'devminor']:
                chunk_props[x] = chunk_props[x].strip()

        for member in self.octal_members:
            # Convert octals to decimal
            chunk_props[member] = int(chunk_props[member], 8)

        # If there is no global header, we need to create one
        if self.need_header:
            # When run against a tree ID, git archive doesn't create
            # a global header.  The first block is just the header for
            # the first file.
            if chunk_props['typeflag'] != 'g':
                self.create_global_header()
                self.create_extended_header()
                self.process_header(chunk_props)
            else:
                self.process_header(chunk_props)
                self.process_extended_header()
            self.need_header = False
        else:
            self.process_header(chunk_props)
            self.process_file_data(chunk_props['size'])

    def fix(self):
        # The gzip file object has its mode as an integer.  We have to
        # access the underlying file object to get the real mode.
        if hasattr(self.fh, "myfileobj"):
            mode = self.fh.myfileobj.mode
        else:
            mode = self.fh.mode

        if 'b' not in mode:
            raise IOError("The input file must be opened in binary mode!")

        try:
            chunk = self.full_read(RECORD_SIZE)
            while chunk != "" and not self.done:
                self.process_chunk(chunk)
                if not self.done:
                    chunk = self.full_read(RECORD_SIZE)
        finally:
            self.fh.close()


if __name__ == '__main__':
    if len(sys.argv) != 5:
        sys.exit("Usage: %s UNIX_TIMESTAMP GIT_HASH TAR_FILE DESTINATION_FILE" % sys.argv[0])

    try:
        timestamp = int(sys.argv[1])
    except:
        sys.exit("UNIX_TIMESTAMP must be an integer")

    gitref = sys.argv[2]
    tar_file = sys.argv[3]
    destination_file = sys.argv[4]

    try:
        dfh = open(destination_file, 'wb')
    except:
        print("Could not open %s" % destination_file)

    try:
        fh = open(tar_file, 'rb')
    except:
        print("Could not read %s" % tar_file)

    reader = TarFixer(fh, dfh, timestamp, gitref)
    reader.fix()
