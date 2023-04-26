from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..fotoware.apitypes import Asset
from .jsonld import jsonldrender

env = Environment(
    loader=FileSystemLoader("app/renderers"),
    autoescape=select_autoescape(),
)


def htmlrender(asset: Asset) -> str:
    template = env.get_template("asset.html.jinja")
    desc = jsonldrender(asset)
    return template.render(asset=desc)
