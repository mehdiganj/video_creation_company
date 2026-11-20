from videogen.templates.avatar import AvatarTemplate
from videogen.templates.base import Template
from videogen.templates.faceless import FacelessTemplate
from videogen.templates.text_card import TextCardTemplate

REGISTRY: dict[str, type[Template]] = {
    "faceless": FacelessTemplate,
    "text_card": TextCardTemplate,
    "avatar": AvatarTemplate,
}


def get_template(name: str) -> Template:
    try:
        return REGISTRY[name]()
    except KeyError as e:
        valid = ", ".join(sorted(REGISTRY))
        raise KeyError(f"Unknown template {name!r}. Valid templates: {valid}") from e
