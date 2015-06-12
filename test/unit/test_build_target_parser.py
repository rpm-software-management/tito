
import unittest
from tito.buildparser import BuildTargetParser
from tito.compat import *  # NOQA
from tito.exception import TitoException


class BuildTargetParserTests(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.valid_branches = ["branch1", "branch2"]

        self.release_target = "project-x.y.z"
        self.releasers_config = RawConfigParser()
        self.releasers_config.add_section(self.release_target)
        self.releasers_config.set(self.release_target, "build_targets",
                                  "branch1:project-x.y.z-candidate")

    def test_parser_gets_correct_targets(self):
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        release_targets = parser.get_build_targets()
        self.assertTrue("branch1" in release_targets)
        self.assertEqual("project-x.y.z-candidate", release_targets["branch1"])
        self.assertFalse("branch2" in release_targets)

    def test_invalid_branch_raises_exception(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  "invalid-branch:project-x.y.z-candidate")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        self.assertRaises(TitoException, parser.get_build_targets)

    def test_missing_semicolon_raises_exception(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  "invalid-branchproject-x.y.z-candidate")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        self.assertRaises(TitoException, parser.get_build_targets)

    def test_empty_branch_raises_exception(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  ":project-x.y.z-candidate")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        self.assertRaises(TitoException, parser.get_build_targets)

    def test_empty_target_raises_exception(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  "branch1:")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        self.assertRaises(TitoException, parser.get_build_targets)

    def test_multiple_spaces_ok(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  "       branch1:project-x.y.z-candidate      ")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        release_targets = parser.get_build_targets()
        self.assertEqual(1, len(release_targets))
        self.assertTrue("branch1" in release_targets)
        self.assertEqual("project-x.y.z-candidate", release_targets["branch1"])

    def test_multiple_branches_supported(self):
        self.releasers_config.set(self.release_target, "build_targets",
                                  "branch1:project-x.y.z-candidate branch2:second-target")
        parser = BuildTargetParser(self.releasers_config, self.release_target,
                                   self.valid_branches)
        release_targets = parser.get_build_targets()
        self.assertEquals(2, len(release_targets))
        self.assertTrue("branch1" in release_targets)
        self.assertEqual("project-x.y.z-candidate", release_targets["branch1"])
        self.assertTrue("branch2" in release_targets)
        self.assertEqual("second-target", release_targets['branch2'])
