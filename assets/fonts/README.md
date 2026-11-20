# Fonts

Both fonts are open-source (OFL-licensed) and safe to commit — see the `*-OFL.txt` files
next to them for the full license text.

| File | Family | Used for | License |
|---|---|---|---|
| `Inter-Variable.ttf` | [Inter](https://github.com/rsms/inter) | English / Latin text | OFL 1.1 (`Inter-OFL.txt`) |
| `Vazirmatn-Regular.ttf`, `Vazirmatn-Bold.ttf` | [Vazirmatn](https://github.com/rastikerdar/vazirmatn) | Farsi / Persian text | OFL 1.1 (`Vazirmatn-OFL.txt`) |

`Inter-Variable.ttf` is a variable font (axes: `opsz`, `wght`). The code selects a weight at
runtime via Pillow's `FreeTypeFont.set_variation_by_name("Regular" | "Bold" | ...)` rather than
shipping a separate static file per weight.

Don't delete or rename these files without also updating `brand.yaml`, which points at them by path.
