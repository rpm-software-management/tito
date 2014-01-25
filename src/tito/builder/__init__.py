# Import our builders so they can be referenced in config as tito.builder.Class
# regardless of which submodule they're in.
from tito.builder.main import \
        Builder, \
        NoTgzBuilder, \
        GemBuilder, \
        CvsBuilder, \
        UpstreamBuilder, \
        SatelliteBuilder, \
        MockBuilder, \
        BrewDownloadBuilder, \
        GitAnnexBuilder

from tito.builder.fetch import FetchBuilder
