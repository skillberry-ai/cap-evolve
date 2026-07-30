from cap_evolve.zoo import ManifestAdapter


class Adapter(ManifestAdapter):
    """toy_calc — everything is declared in ../benchmark.yaml."""

    manifest_path = __file__
