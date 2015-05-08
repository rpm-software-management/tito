# Import our builders so they can be referenced in config as tito.builder.Class
# regardless of which submodule they're in.

# flake8: noqa

from tito.builder.main import \
    Builder, \
    NoTgzBuilder, \
    GemBuilder, \
    UpstreamBuilder, \
    SatelliteBuilder, \
    MockBuilder, \
    BrewDownloadBuilder, \
    GitAnnexBuilder, \
    MeadBuilder

from tito.builder.fetch import FetchBuilder
