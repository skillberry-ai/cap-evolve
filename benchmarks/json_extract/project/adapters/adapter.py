from cap_evolve.zoo import ManifestAdapter


class Adapter(ManifestAdapter):
    """json_extract — everything is declared in ../benchmark.yaml."""

    manifest_path = __file__
