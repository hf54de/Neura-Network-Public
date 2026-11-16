from pathlib import Path
from sys import argv

from PyInstaller.archive.readers import CArchiveReader


def read_rust_exe(exe, rust_dll):
    bundle = CArchiveReader(str(exe))
    member = next(
        (name for name in bundle.toc if name.replace(chr(92), "/") == "rust/training.dll"),
        None,
    )
    if member is None:
        raise SystemExit("Die Rust-DLL fehlt in der erstellten EXE.")
    if bundle.extract(member) != rust_dll.read_bytes():
        raise SystemExit("Die eingebettete Rust-DLL stimmt nicht mit der Quelldatei überein.")

    return bundle


def verify_public_exe(exe, rust_dll, version_file):
    bundle = read_rust_exe(exe, rust_dll)
    try:
        embedded_version = bundle.extract("VERSION.txt").decode("utf-8-sig").strip()
        archive_name = next(name for name in bundle.toc if name.lower().endswith(".pyz"))
        modules = bundle.open_embedded_archive(archive_name).toc
    except (KeyError, StopIteration, UnicodeError):
        raise SystemExit("Programmversion oder Modulliste fehlt in der EXE.")
    if embedded_version != version_file.read_text(encoding="utf-8-sig").strip():
        raise SystemExit("Die Version der Rust-EXE passt nicht zu VERSION.txt. Bitte neu bauen.")
    author = {"authorhtmlexport", "forwardhtmlexport", "trainingclipexport", "characteristicclipexport"}
    if author.intersection(modules):
        raise SystemExit("Dies ist die Autoren-EXE. Bitte Option 1 der Rust-BAT verwenden.")
    if "rusttraining" not in modules:
        raise SystemExit("Die Python-Anbindung fuer Rust fehlt in der EXE.")


def publish_exe(staged_exe, rust_dll, destination):
    read_rust_exe(staged_exe, rust_dll)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        staged_exe.replace(destination)
    except PermissionError as error:
        raise SystemExit(
            f"Die Ziel-EXE ist gesperrt. Bitte die Testversion schließen. ({error})"
        ) from error


if __name__ == "__main__":
    if argv[1:2] == ["--check-public"]:
        verify_public_exe(*map(Path, argv[2:]))
    else:
        publish_exe(*map(Path, argv[1:]))
