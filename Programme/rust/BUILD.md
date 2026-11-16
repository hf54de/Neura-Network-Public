# Build the Windows Rust DLL

Use the 64-bit Windows GNU Rust toolchain used by this release.

```powershell
rustup toolchain install 1.100.0-x86_64-pc-windows-gnu
py -3.14 -B build/build_training_dll.py
```

Run the commands from the program folder that contains `main.py`. The build
script writes `rust/training.dll`. To use a portable toolchain, set
`NEURONNET_RUSTC` to the full path of its compatible `rustc.exe`.

For the Windows EXE, install PySide6 and PyInstaller for 64-bit Python 3.14 and
run `RUST-EXE-erstellen.bat` from the repository root. Choose option 1 for the
public build. The BAT builds the DLL if it is missing and embeds it in the EXE.

See `licenses/` for the notices that accompany the Rust DLL.
