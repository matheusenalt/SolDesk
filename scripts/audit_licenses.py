"""Inventário local de licenças; não substitui a leitura dos termos upstream."""

import json
from collections import Counter
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_report(name, rows):
    (ROOT / "docs" / name).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main():
    pins = (ROOT / "backend/requirements.lock").read_text().splitlines()
    python_rows = []
    for pin in pins:
        if "==" not in pin:
            continue
        name, version = pin.split("==", 1)
        dist = metadata.distribution(name)
        if dist.version != version:
            raise ValueError(f"Versão instalada difere do lock: {name}")
        python_rows.append(
            {
                "name": name,
                "version": version,
                "license": dist.metadata.get("License-Expression")
                or dist.metadata.get("License"),
                "classifiers": [
                    c
                    for c in dist.metadata.get_all("Classifier", [])
                    if c.startswith("License ::")
                ],
                "license_files": [
                    str(p)
                    for p in dist.files or []
                    if any(
                        word in str(p).lower()
                        for word in ("license", "copying", "notice")
                    )
                ],
            }
        )
    lock = json.loads((ROOT / "web/package-lock.json").read_text())
    npm_rows = [
        {
            "package": name,
            "version": item.get("version"),
            "license": item.get("license"),
            "optional": bool(item.get("optional")),
            "dev": bool(item.get("dev")),
        }
        for name, item in lock["packages"].items()
        if name
    ]
    write_report("LICENCAS_PYTHON.json", python_rows)
    write_report("LICENCAS_NPM.json", npm_rows)
    print("Python:", len(python_rows), Counter(r["license"] for r in python_rows))
    print("npm:", len(npm_rows), Counter(r["license"] for r in npm_rows))
    print(
        "npm sem licença declarada:",
        [r["package"] for r in npm_rows if not r["license"]],
    )


if __name__ == "__main__":
    main()
