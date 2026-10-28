"""Colour themes.

Every flat colour in the diorama comes from here, so the whole scene can be
re-skinned by flipping one environment variable:

    THEME=purple  (the original)      THEME=green  (default)

Only one colour per material is allowed -- that rule still holds, the theme
just says which colour.
"""
import os

# ---------------------------------------------------------------- purple (v1-v4)
PURPLE = dict(
    BASE="#D4BEF3", MID="#AC84DE", DEEP="#8C66C8",
    PAINT_BASE="#D4BEF3", PAINT_MID="#B592E8", PAINT_DEEP="#9B76D8",
    GRASS="#584499", PATHC="#7E56BC",
    FLOWER="#BFE4FF", FLOWER_CORE="#EAF6FF", STEMC="#4B3A92",
    LEAF="#7B5AC4", LEAF_SIMPLE="#8E6BD8",
    BARK="#57427C", BARK_DARK="#3B2E58", BARK_LIGHT="#7A61A8",
    FRAME="#3E3160", DECK="#6B51A8", GLASS="#F0E8FF", TATAMI="#D8C8F4",
    WOOD2="#6A539B", CUSHION="#9478D2", LAMP="#FFC98A",
    SKY_TOP="#5B4590", SKY_MID="#4A3575", SKY_HOR="#A98BD8", CLOUD="#C3B0E4",
    AMBIENT="#D2C0F4", WORLD_BG="#CFBCF2", FOG="#E4D6FF", BEAM="#EFE4FF",
)

# ---------------------------------------------------------------- green (v5)
# Same value structure as the purple set (light base -> saturated mid -> dark
# grass), just walked around the hue wheel: sunlit spring turf.
# NB the camera only ever sees the dome's MID -> TOP band, so those two carry
# the visible backdrop; HOR only shows up in steeper or wider shots.
GREEN = dict(
    BASE="#D5EFA6", MID="#A6D96A", DEEP="#79BE43",
    PAINT_BASE="#D5EFA6", PAINT_MID="#BCE287", PAINT_DEEP="#9DD06A",
    GRASS="#2F823D", PATHC="#78875E",
    FLOWER="#BFE4FF", FLOWER_CORE="#EAF6FF", STEMC="#3A6B2A",
    LEAF="#58B33A", LEAF_SIMPLE="#6DC44C",
    BARK="#4A3F2A", BARK_DARK="#2F3520", BARK_LIGHT="#77804F",
    FRAME="#2A3D26", DECK="#4C6B3C", GLASS="#EAF8E8", TATAMI="#E6F0C8",
    WOOD2="#43613A", CUSHION="#7FA75A", LAMP="#FFC98A",
    SKY_TOP="#B6DDC6", SKY_MID="#7FB49B", SKY_HOR="#E8F6E4", CLOUD="#F2FBF0",
    AMBIENT="#CFEFD0", WORLD_BG="#CBE8CF", FOG="#E2F2DC", BEAM="#F6FDF4",
)

# ---------------------------------------------------------------- gold (v6)
# Ripe wheat field at golden hour: same value ladder again (pale straw base ->
# amber strokes -> dark ochre grass), with a dusty warm horizon so the backdrop
# does not collapse into the ground's yellow.
GOLD = dict(
    BASE="#F5E39C", MID="#E9CE6A", DEEP="#C9A438",
    PAINT_BASE="#F5E39C", PAINT_MID="#E9CE6A", PAINT_DEEP="#D9B845",
    GRASS="#8B6A20", PATHC="#A89257",
    FLOWER="#FFE9CF", FLOWER_CORE="#FFFBF2", STEMC="#7A5C22",
    LEAF="#E39A28", LEAF_SIMPLE="#EFB23C",
    BARK="#4A3A28", BARK_DARK="#33291C", BARK_LIGHT="#7A6845",
    FRAME="#3A2A1A", DECK="#7A5A32", GLASS="#FFF6E4", TATAMI="#E9D7A8",
    WOOD2="#6A4C2A", CUSHION="#C89B4E", LAMP="#FFC98A",
    SKY_TOP="#F8E7CE", SKY_MID="#D3A87F", SKY_HOR="#FFF8EE", CLOUD="#FFFDF4",
    AMBIENT="#F8E9C8", WORLD_BG="#F3E1B8", FOG="#F8EBCD", BEAM="#FFF9E8",
)

_PRESETS = {"purple": PURPLE, "green": GREEN, "gold": GOLD}
THEME = os.environ.get("THEME", "gold").lower()
if THEME not in _PRESETS:
    raise SystemExit("unknown THEME %r, expected one of %s" % (THEME, list(_PRESETS)))


class _Theme:
    """Attribute access with a loud failure, so a typo cannot silently pass."""

    def __init__(self, name):
        self.name = name
        self._d = _PRESETS[name]

    def __getattr__(self, key):
        try:
            return self._d[key]
        except KeyError:
            raise AttributeError("theme %r has no colour %r" % (self.name, key))

    def __getitem__(self, key):
        return self._d[key]


T = _Theme(THEME)
