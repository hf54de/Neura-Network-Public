"""Build the Windows training DLL with the documented Rust toolchain."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

TOOLCHAIN = "1.100.0-x86_64-pc-windows-gnu"
ROOT = Path(__file__).resolve().parent.parent


def main():
    compiler = os.environ.get("NEURONNET_RUSTC")
    rustc = [compiler] if compiler else ["rustup", "run", TOOLCHAIN, "rustc"]
    try:
        info = subprocess.check_output([*rustc, "-vV"], encoding="utf-8")
        if "release: 1.100.0" not in info.splitlines() or "host: x86_64-pc-windows-gnu" not in info.splitlines():
            raise SystemExit(f"Rust-Toolchain {TOOLCHAIN} wird benoetigt.")
        with TemporaryDirectory(prefix=".training-", dir=ROOT / "rust") as temp:
            dll = Path(temp) / "training.dll"
            subprocess.run([
                *rustc, "--edition=2024", "--crate-type=cdylib", "-C", "opt-level=3",
                str(ROOT / "rust" / "training.rs"), "-o", str(dll),
            ], check=True)
            dll.replace(ROOT / "rust" / "training.dll")
    except FileNotFoundError:
        raise SystemExit(f"Rust fehlt. Toolchain installieren: rustup toolchain install {TOOLCHAIN}")


if __name__ == "__main__":
    main()
