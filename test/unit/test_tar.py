import hashlib
import os
import unittest

from StringIO import StringIO
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
        return self.hash_buffer(open(filename, 'rb').read())

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
        self.fh = open(self.test_file)
        self.tarfixer.fh = self.fh
        self.tarfixer.fix()
        self.assertEqual(self.reference_hash, self.hash_buffer("".join(self.out.buflist)))

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

    def test_create_extended_header(self):
        self.tarfixer.create_extended_header()
        header = "".join(self.out.buflist)
        self.assertEqual(512, len(header))
        self.assertEqual("52 comment=%s\n" % EXPECTED_REF, header[:52])
        self.assertEqual("\x00" * (512 - 53), header[53:])

    def test_calculate_checksume(self):
        result = self.tarfixer.calculate_checksum(['\x01', '\x02', '\x03', '\x04'])
        expected_result = 10 + ord(" ") * 8
        self.assertEqual("%07o\x00" % expected_result, result)

    def test_encode_header(self):
        mode = 123
        chunk = {
            'mode': mode,
            'name': 'hello',
        }
        result = self.tarfixer.encode_header(chunk, ['mode', 'name'])
        expected_result = ["%07o\x00" % mode, 'hello']
        self.assertEqual(result, expected_result)
