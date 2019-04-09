# coding=utf-8
import hashlib
import os
import tarfile
import unittest
import io

from tito.compat import StringIO, ensure_binary
from tito.tar import TarFixer
from mock import Mock

EXPECTED_TIMESTAMP = 1429725106
EXPECTED_REF = "3518d720bff20db887b7a5e5dddd411d14dca1f9"


class TarTest(unittest.TestCase):
    def setUp(self):
        self.out = io.BytesIO()
        self.tarfixer = TarFixer(None, self.out, EXPECTED_TIMESTAMP, EXPECTED_REF)
        self.utf8_containing_file = os.path.join(os.path.dirname(__file__), 'resources', 'les_misérables.tar')
        self.utf8_file = os.path.join(os.path.dirname(__file__), 'resources', 'archivé.tar')
        self.test_file = os.path.join(os.path.dirname(__file__), 'resources', 'archive.tar')
        self.reference_file = os.path.join(os.path.dirname(__file__), 'resources', 'archive-fixed.tar')
        self.reference_hash = self.hash_file(self.reference_file)

    def tearDown(self):
        self.out = None

    def hash_file(self, filename):
        file_bytes = open(filename, 'rb').read()
        return self.hash_buffer(file_bytes)

    def hash_buffer(self, buf):
        hasher = hashlib.sha256()
        hasher.update(buf)
        return hasher.hexdigest()

    def _irregular_reader(self, items):
        def item_read(read_length):
            try:
                item = items.pop(0)
            except IndexError:
                # If no more items, the buffer is empty and would return empty string
                return ''

            return item.read(read_length)

        mock_fh = Mock()
        mock_fh.read = Mock()
        mock_fh.read.side_effect = item_read

        return mock_fh

    def test_full_read(self):
        items = [StringIO("1" * 5), StringIO("1" * 2), StringIO("1" * 6)]
        self.tarfixer.fh = self._irregular_reader(items)
        self.assertEqual("1" * 10, self.tarfixer.full_read(10))

    def test_full_read_buffer_underflow(self):
        input = StringIO("1" * 9)
        self.tarfixer.fh = input
        self.assertRaises(IOError, self.tarfixer.full_read, 10)

    def test_full_read_eventual_buffer_underflow(self):
        items = [StringIO("1" * 5), StringIO("1" * 2), StringIO("1" * 2)]
        self.tarfixer.fh = self._irregular_reader(items)
        self.assertRaises(IOError, self.tarfixer.full_read, 10)

    def test_fix(self):
        self.fh = open(self.test_file, 'rb')
        self.tarfixer.fh = self.fh
        self.tarfixer.fix()
        self.assertEqual(self.reference_hash, self.hash_buffer(self.out.getvalue()))

    def test_fix_fails_unless_file_in_binary_mode(self):
        self.fh = open(self.test_file, 'r')
        self.tarfixer.fh = self.fh
        self.assertRaises(IOError, self.tarfixer.fix)

    def test_padded_size_length_small(self):
        length = 10
        block_size = 512
        self.assertEqual(512, self.tarfixer.padded_size(length, block_size))

    def test_padded_size_length_spot_on(self):
        length = 512
        block_size = 512
        self.assertEqual(512, self.tarfixer.padded_size(length, block_size))

    def test_padded_size_length_over(self):
        length = 513
        block_size = 512
        self.assertEqual(1024, self.tarfixer.padded_size(length, block_size))

    def test_padded_size_length_long(self):
        length = 82607
        block_size = 512
        self.assertEqual(82944, self.tarfixer.padded_size(length, block_size))

    def test_create_extended_header(self):
        self.tarfixer.create_extended_header()
        header = self.out.getvalue()
        self.assertEqual(512, len(header))
        self.assertEqual(ensure_binary("52 comment=%s\n" % EXPECTED_REF), header[:52])
        self.assertEqual(ensure_binary("\x00" * (512 - 53)), header[53:])

    def test_calculate_checksum(self):
        fields = {
            'a': '\x01',
            'b': '\x02',
            'c': '\x03',
            'd': '\x04',
        }
        self.tarfixer.struct_members = list(fields.keys()) + ['checksum']
        result = self.tarfixer.calculate_checksum(fields)
        expected_result = 10 + ord(" ") * 8
        self.assertEqual("%07o\x00" % expected_result, result)

    def test_encode_header(self):
        mode = 123
        chunk = {
            'mode': mode,
            'name': 'hello',
        }
        result = self.tarfixer.encode_header(chunk, ['mode', 'name'])
        expected_result = ["%07o\x00" % mode, "hello"]
        expected_result = list(map(lambda x: ensure_binary(x), expected_result))
        self.assertEqual(expected_result, result)

    def test_utf8_file(self):
        # The goal of this test is to *not* throw a UnicodeDecodeError
        self.fh = open(self.utf8_file, 'rb')
        self.tarfixer.fh = self.fh
        self.tarfixer.fix()

        self.assertEqual(self.reference_hash, self.hash_buffer(self.out.getvalue()))

        # rewind the buffer
        self.out.seek(0)
        try:
            tarball = tarfile.open(fileobj=self.out, mode="r")
        except tarfile.TarError:
            self.fail("Unable to open generated tarball")

    def test_utf8_containing_file(self):
        # # The goal of this test is to *not* blow up due to a corrupted tarball
        self.fh = open(self.utf8_containing_file, 'rb')
        self.tarfixer.fh = self.fh
        self.tarfixer.fix()

        # rewind the buffer
        self.out.seek(0)
        try:
            tarball = tarfile.open(fileobj=self.out, mode="r")
        except tarfile.TarError as e:
            self.fail("Unable to open generated tarball: %s" % e)
