# Institutional visual identity

Joe's direction (31 October 2026): restore the teaser to the original institutional
identity and make the overall palette more like Japan IR Index: a restrained
Wall Street research/publication style.

The original mamatch house sheet used navy, white paper, fine rules and serif
headlines. Kimi's standalone prototype introduced yellow, sky blue and olive fills.
The current Japan IR Index navy edition (its last-loaded `redesign.css`) is the
reference for this update: https://japanirindex.com/en/.

Shared application tokens live in `web/static/palette.css`:

| Role | Colour |
| --- | --- |
| Structure / primary action | `#0b2545` navy |
| Secondary accent / focus | `#1f4e8c` blue |
| Paper | `#ffffff` |
| Neutral surface | `#f7f8fa` |
| Quiet notice / control surface | `#eef2f8` |
| Main text | `#1a1f2b` |
| Secondary text | `#3a414c` |
| Muted text | `#5b6472` |

Use serif headlines, readable sans-serif body copy, tabular figures, fine borders
and squared controls. Avoid decorative yellow/gold, olive and bright sky-blue
panels. Red/amber/green remain available for meaningful error/warning/success states.
The main site, English standalone teaser, Chinese teaser and document demos share
the palette. Their differing layouts are intentional; language and workflow controls
remain as previously verified.
