import hashlib
import os
import unittest

from tito.compat import StringIO, encode_bytes
from tito.tar import TarFixer
from mock import Mock

EXPECTED_TIMESTAMP = 1429725106
EXPECTED_REF = "3518d720bff20db887b7a5e5dddd411d14dca1f9"


class TarTest(unittest.TestCase):
    def setUp(self):
        self.out = StringIO()
        self.tarfixer = TarFixer(None, self.out, EXPECTED_TIMESTAMP, EXPECTED_REF)
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
        self.assertEqual(self.reference_hash, self.hash_buffer(encode_bytes(self.out.getvalue(), "utf8")))

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
        self.assertEqual("52 comment=%s\n" % EXPECTED_REF, header[:52])
        self.assertEqual("\x00" * (512 - 53), header[53:])

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
        expected_result = list(map(lambda x: encode_bytes(x, "utf8"), expected_result))
        self.assertEqual(expected_result, result)
