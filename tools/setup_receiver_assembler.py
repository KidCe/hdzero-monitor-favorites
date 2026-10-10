"""Install one pinned portable assembler into a user cache, without device access."""
import argparse
import hashlib
import urllib.request
import zipfile
from pathlib import Path

from monitor_receiver_source import ASSEMBLER_SHA256

URL='https://www.mikekohn.net/downloads/naken_asm/naken_asm-2024-11-03.zip'
ARCHIVE_SHA256='8c4e7b3ba2a9782922bd6d02592ca4b974bb986bba4b757abdf0c50a3cfbca08'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools-dir',type=Path,default=Path.home() / '.cache' / 'hdzero-monitor-tools')
    args=parser.parse_args()
    root=args.tools_dir.resolve()
    root.mkdir(parents=True,exist_ok=True)
    archive=root/'naken_asm-2024-11-03.zip'
    if not archive.exists():
        with urllib.request.urlopen(URL,timeout=60) as response:
            data=response.read()
        if hashlib.sha256(data).hexdigest()!=ARCHIVE_SHA256:
            raise ValueError('Downloaded assembler archive hash differs from pinned acquisition')
        archive.write_bytes(data)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=ARCHIVE_SHA256:
        raise ValueError('Assembler archive hash mismatch')
    destination=root/'naken_asm-2024-11-03'
    executable=destination/'naken_asm-2024-11-03/naken_asm.exe'
    if not executable.exists():
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                target=(destination/name).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ValueError('Archive path escapes cache directory')
            bundle.extractall(destination)
    if hashlib.sha256(executable.read_bytes()).hexdigest()!=ASSEMBLER_SHA256:
        raise ValueError('Portable assembler executable hash mismatch')
    print(executable)


if __name__=='__main__':
    main()
