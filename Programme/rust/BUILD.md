# Build the public Windows EXE

The commands below build the Rust training DLL and the public NeuronNet EXE
for 64-bit Windows. The executable uses the version in `VERSION.txt`.

Use 64-bit Python 3.14 with the Windows Python launcher and the 64-bit Windows
GNU Rust toolchain. The tested Python version is 3.14.7. Run these commands
in PowerShell from the extracted public source archive:

```powershell
Set-Location .\Programme
py -3.14 -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install "PySide6==6.11.1" "PyInstaller==6.21.0"
rustup toolchain install 1.100.0-x86_64-pc-windows-gnu
```

If you are working in the development tree, use `Set-Location .\Programme-Rust`
for the first command. For a portable Rust installation, set `NEURONNET_RUSTC`
to the full path of its compatible `rustc.exe` before building.

From the directory that contains `main.py`, run:

```powershell
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -B .\build\build_training_dll.py
if ($LASTEXITCODE -ne 0) { throw "Rust DLL build failed." }

$previousPath = $env:PATH
$previousFlavor = $env:NEURONNET_BUILD_FLAVOR
try {
    $env:NEURONNET_BUILD_FLAVOR = 'public'
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
    & $python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller-rust build\NeuronNet-Rust.spec
    if ($LASTEXITCODE -ne 0) { throw "NeuronNet EXE build failed." }
} finally {
    $env:PATH = $previousPath
    $env:NEURONNET_BUILD_FLAVOR = $previousFlavor
}
```

The resulting `dist\NeuronNet.exe` contains the Rust DLL. The temporary PATH
used for PyInstaller keeps unrelated third-party DLL directories out of the
build. See `rust/licenses/` for the notices that accompany the Rust DLL.
