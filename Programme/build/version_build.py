# -------------------------------------------------------------------------------------------------
# Datei: version_build.py
# Zweck: Bereitet Versionsdaten für einen reproduzierbaren Windows-Build vor.
# Letzte Änderung: 16.08.2026
# Copyright © 2026 Helwig Fülling
# -------------------------------------------------------------------------------------------------
"""Bereitet Versionsdaten für einen reproduzierbaren Windows-Build vor."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path


PROGRAM_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = PROGRAM_DIR / "VERSION.txt"
CHANGELOG_FILE = PROGRAM_DIR.parent / "CHANGELOG.md"
VERSION_INFO_FILE = PROGRAM_DIR / "build" / "version_info.txt"
STATE_FILE = PROGRAM_DIR / "build" / ".version_build_state.json"
VERSION_PATTERN = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$",
    re.IGNORECASE,
)


def read_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def restore_state() -> bool:
    if not STATE_FILE.is_file():
        return False

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    changelog = CHANGELOG_FILE if state.get("central_changelog") else PROGRAM_DIR / "CHANGELOG.md"
    for path, content in (
        (VERSION_FILE, state.get("version_content")),
        (changelog, state.get("changelog_content")),
        (VERSION_INFO_FILE, state.get("version_info_content")),
    ):
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write_text(path, content)

    STATE_FILE.unlink(missing_ok=True)
    return True


def version_parts(version: str) -> tuple[int, int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError("Ungültige Versionsnummer")
    major, minor, patch = (int(match.group(index)) for index in (1, 2, 3))
    prerelease_number = int(match.group(5) or 0)
    parts = (major, minor, patch, prerelease_number)
    if any(number > 65535 for number in parts):
        raise ValueError("Jeder numerische Versionsteil muss kleiner als 65536 sein")
    return parts


def windows_version_information(version: str) -> str:
    major, minor, patch, build = version_parts(version)
    numeric = f"{major}.{minor}.{patch}.{build}"
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040704B0',
        [StringStruct('CompanyName', 'Helwig Fülling'),
         StringStruct('FileDescription', 'NeuronNet – Grafischer Editor für neuronale Netzwerke'),
         StringStruct('FileVersion', '{numeric}'),
         StringStruct('InternalName', 'NeuronNet'),
         StringStruct('LegalCopyright', '© 2026 Helwig Fülling'),
         StringStruct('OriginalFilename', 'NeuronNet.exe'),
         StringStruct('ProductName', 'NeuronNet'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""


def prepare() -> int:
    if restore_state():
        print("Ein unvollständiger früherer Build wurde zurückgesetzt.")

    current = (read_text(VERSION_FILE) or "0.9.0-beta.1").strip()
    try:
        version_parts(current)
    except ValueError as error:
        print(f"FEHLER: VERSION.txt enthält keine gültige Version: {error}")
        return 1

    print()
    print(f"Aktuelle Version: {current}")
    entered = input(
        "Neue Version (Eingabetaste = beibehalten): "
    ).strip()
    new_version = entered or current

    try:
        version_parts(new_version)
    except ValueError as error:
        print(f"FEHLER: {error}.")
        print("Beispiele: 1.0.0, 1.0.1 oder 0.9.0-beta.2")
        return 1

    change_descriptions = []
    if new_version != current:
        print()
        print("Änderungen bitte einzeln eingeben.")
        print("Eine leere Eingabe beendet die Liste.")
        while True:
            description = input(
                f"Änderung {len(change_descriptions) + 1}: "
            ).strip()
            if description:
                change_descriptions.append(description)
                continue
            if change_descriptions:
                break
            print("Bei einer neuen Version ist mindestens eine Beschreibung erforderlich.")

    print()
    print(f"Build-Version: {new_version}")
    if change_descriptions:
        print("Änderungen:")
        for description in change_descriptions:
            print(f"- {description}")
    confirmation = input("Build jetzt starten? [J/N]: ").strip().lower()
    if confirmation not in {"j", "ja", "y", "yes"}:
        print("Build abgebrochen.")
        return 2

    state = {
        "version_content": read_text(VERSION_FILE),
        "changelog_content": read_text(CHANGELOG_FILE),
        "version_info_content": read_text(VERSION_INFO_FILE),
        "central_changelog": True,
        "new_version": new_version,
    }
    write_text(
        STATE_FILE,
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
    )

    write_text(VERSION_FILE, new_version + "\n")
    if change_descriptions:
        existing = read_text(CHANGELOG_FILE) or "# Änderungsverlauf\n"
        heading = f"## {new_version} – {date.today():%d.%m.%Y}"
        if heading in existing or re.search(
            rf"^##\s+{re.escape(new_version)}(?:\s|$)",
            existing,
            flags=re.MULTILINE,
        ):
            print("FEHLER: Diese Version ist bereits im CHANGELOG vorhanden.")
            restore_state()
            return 1
        title, separator, remainder = existing.partition("\n")
        change_list = "\n".join(
            f"- {description}" for description in change_descriptions
        )
        new_entry = f"\n\n{heading}\n\n{change_list}\n"
        updated = title + new_entry
        if separator and remainder.strip():
            updated += "\n" + remainder.lstrip("\n")
        write_text(CHANGELOG_FILE, updated.rstrip() + "\n")

    write_text(VERSION_INFO_FILE, windows_version_information(new_version))
    return 0


def commit() -> int:
    STATE_FILE.unlink(missing_ok=True)
    return 0


def rollback() -> int:
    if restore_state():
        print("Versionsnummer und Änderungsverlauf wurden zurückgesetzt.")
    return 0


def choose_edition() -> int:
    editions = {"1": ("Öffentliche Rust-EXE", 10), "2": ("Rust-Autoren-EXE mit HTML-Exporten", 11)}
    print("Welche EXE soll erstellt werden?")
    print("  1  Öffentliche Rust-EXE")
    print("  2  Rust-Autoren-EXE mit HTML-Exporten")
    print("  0  Abbrechen")
    print()
    while True:
        choice = input("Auswahl [1]: ").strip() or "1"
        if choice == "0":
            print("Build abgebrochen.")
            return 2
        if choice in editions:
            label, edition_code = editions[choice]
            print(f"\nGewählt: {label}")
            result = prepare()
            return edition_code if result == 0 else result
        print("Ungültige Auswahl. Bitte 1, 2 oder 0 eingeben.")


def main() -> int:
    command = sys.argv[1].lower() if len(sys.argv) > 1 else "prepare"
    if command in {"choose", "prepare"}:
        try:
            return choose_edition() if command == "choose" else prepare()
        except (EOFError, KeyboardInterrupt):
            print("\nBuild abgebrochen.")
            return 2
    if command == "commit":
        return commit()
    if command == "rollback":
        return rollback()
    print("Verwendung: version_build.py [choose|prepare|commit|rollback]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
