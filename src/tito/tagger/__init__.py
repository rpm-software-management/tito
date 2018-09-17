# flake8: noqa

from tito.tagger.main import \
    VersionTagger, \
    ReleaseTagger, \
    ForceVersionTagger

from tito.tagger.rheltagger import RHELTagger
from tito.tagger.zstreamtagger import zStreamTagger
from tito.tagger.cargobump import CargoBump
from tito.tagger.susetagger import SUSETagger
