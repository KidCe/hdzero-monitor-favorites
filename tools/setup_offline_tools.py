"""Download hash-pinned portable analysis tools; does not access the Monitor."""

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


PACKAGES = {
    "ghidra": (
        "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip",
        "ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db",
    ),
    "jdk": (
        "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip",
        "f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e",
    ),
    "unicorn": (
        "https://files.pythonhosted.org/packages/70/3d/de7be9bd1addabe6d8a1369381f8a080400c349850e978689c5e18287957/unicorn-2.1.4-cp37-abi3-win_amd64.whl",
        "d7107500c64ce5c168fbff6bef9485b5db1350050036f4cea568650cf8bdbdf5",
    ),
}


def download(name, root):
    url, expected = PACKAGES[name]
    path = root / url.rsplit("/", 1)[1]
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Existing {name} archive hash mismatch")
        return path
    partial = path.with_suffix(path.suffix + ".partial")
    digest = hashlib.sha256()
    size, next_progress = 0, 0
    request = urllib.request.Request(url, headers={"User-Agent": "HDZero-offline-analysis"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
            digest.update(chunk)
            size += len(chunk)
            if size >= next_progress:
                print(f"{name}: {size // (1024 * 1024)} MiB downloaded", flush=True)
                next_progress = size + 64 * 1024 * 1024
    if digest.hexdigest() != expected:
        raise ValueError(f"Downloaded {name} archive hash mismatch")
    partial.rename(path)
    return path


def extract(archive, root):
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            target = (root / member.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("Archive contains a path outside the tool directory")
        source.extractall(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(download, name, root) for name in PACKAGES}
        archives = {name: future.result() for name, future in futures.items()}
    ghidra = root / "ghidra_12.1.4_PUBLIC"
    jdk = root / "jdk-21.0.12.1+1"
    if not (jdk / "bin/java.exe").exists():
        print("Extracting portable JDK", flush=True)
        extract(archives["jdk"], root)
    if not (ghidra / "support/analyzeHeadless.bat").exists():
        print("Extracting Ghidra", flush=True)
        extract(archives["ghidra"], root)
    if not (jdk / "bin/java.exe").exists() or not ghidra.is_dir():
        raise RuntimeError("Unexpected archive root layout")
    # Scope the Java override to this portable Ghidra installation.
    launch = ghidra / "support/launch.properties"
    lines = launch.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if not line.startswith("JAVA_HOME_OVERRIDE=")]
    lines.append("JAVA_HOME_OVERRIDE=" + jdk.as_posix())
    launch.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dependencies = root / "python-libs"
    if not (dependencies / "unicorn").is_dir():
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target",
                        str(dependencies), str(archives["unicorn"])], check=True)
    manifest = {"ghidra": str(ghidra), "jdk": str(jdk), "python_dependencies": str(dependencies),
                "archives": {name: {"url": info[0], "sha256": info[1]} for name, info in PACKAGES.items()}}
    (root / "tools.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
