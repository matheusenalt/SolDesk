"""Fonte única de tokens → CSS web e constantes mobile; validação WCAG."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels
    ]
    return sum(
        v * weight for v, weight in zip(linear, [0.2126, 0.7152, 0.0722], strict=True)
    )


def contrast(a, b):
    first, second = sorted([luminance(a), luminance(b)])
    return (second + 0.05) / (first + 0.05)


def generate(check=False):
    data = json.loads((ROOT / "docs/tokens.json").read_text(encoding="utf-8"))
    colors = data["palette"] | data["extensions"]
    css = ["/* Gerado por scripts/tokens.py; editar docs/tokens.json. */", "@theme {"]
    css += [f"  --color-{key}: {value};" for key, value in data["palette"].items()]
    css += [
        f"  --spacing: {data['spacing']};",
        f"  --radius-xl: {data['radius-xl']};",
        "}",
    ]
    mobile = {}
    for theme, mapping in data["themes"].items():
        mobile[theme] = {key: colors[value] for key, value in mapping.items()}
        css.append(":root {" if theme == "light" else '[data-theme="dark"] {')
        css += [f"  --{key}: {colors[value]};" for key, value in mapping.items()]
        css.append("}")
        pairs = [("on-primary", "primary", 4.5), ("on-accent", "accent", 4.5)]
        for background in ("surface", "panel"):
            pairs += [
                (key, background, 4.5)
                for key in (
                    "text",
                    "muted",
                    "success",
                    "error",
                    "warning",
                    "information",
                )
            ]
            pairs.append(("control-border", background, 3))
        for foreground, background, minimum in pairs:
            ratio = contrast(colors[mapping[foreground]], colors[mapping[background]])
            print(f"{theme:5} {foreground:15}/{background:8}: {ratio:.2f}:1")
            if ratio < minimum:
                raise SystemExit(
                    f"Contraste insuficiente: {theme}/{foreground}/{background}"
                )
    outputs = {
        ROOT / "web/src/tokens.css": "\n".join(css) + "\n",
        ROOT / "mobile/theme.ts": (
            "// Gerado por scripts/tokens.py; não editar.\n"
            "export const themes = " + json.dumps(mobile, indent=2) + " as const;\n"
        ),
    }
    for path, content in outputs.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Tokens desatualizados: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
