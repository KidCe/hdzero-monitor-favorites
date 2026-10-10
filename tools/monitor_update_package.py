"""Package a pinned rebuilt receiver in the Monitor update format, entirely offline."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from monitor_receiver_decode import ENCODE_TABLE, DECODE_TABLE, DECODED_SHA256

OFFICIAL_SHA256='6b7f7cd53be329eaa4059b7b40c2e3e8f2fad1d8ecd94bfe0cb7a228131f7041'
DEVICE_MSTAR_SHA256='68ffa3d3a94058e8e605a9f48179305502893c4c426706525aac4e1df5f9e887'
FAVORITES_SHA256='0083c42f11e22154168bcac949acccf32b0df709af23a9a1e430b0ab278cbd33'  # v7 P-band scan list; v6 d12c1bb9..., v5 16f20e26..., v4 7c4970a5...
COMPONENTS=('5680','fpga','8339')
SOURCE='https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def split_container(data):
    if len(data)<14:
        raise ValueError('Truncated update header')
    lengths=struct.unpack_from('<3I',data,2)
    if not (0<lengths[0]<65536 and all(0<n<10000000 for n in lengths[1:])):
        raise ValueError('Component length violates inspected programmer bounds')
    if sum(lengths)+14!=len(data):
        raise ValueError('Container length does not match component lengths')
    position=14
    payloads={}
    for name,length in zip(COMPONENTS,lengths):
        payloads[name]=data[position:position+length]
        position+=length
    return data[:2],payloads


def join_container(prefix,payloads):
    if len(prefix)!=2 or set(payloads)!=set(COMPONENTS):
        raise ValueError('Unexpected prefix or components')
    data=prefix+struct.pack('<3I',*(len(payloads[name]) for name in COMPONENTS))+b''.join(payloads[name] for name in COMPONENTS)
    split_container(data)
    return data


def make_package(official,receiver,device_mstar=None):
    """device_mstar=None builds a release package: FPGA and MStar exactly as in official 1.1.1."""
    if digest(official)!=OFFICIAL_SHA256:
        raise ValueError('Only the pinned official 1.1.1 baseline is supported')
    if device_mstar is not None and (len(device_mstar)!=16*1024*1024 or digest(device_mstar)!=DEVICE_MSTAR_SHA256):
        raise ValueError('Pinned installed MStar backup is required to preserve filesystem state')
    receiver_hash=digest(receiver)
    if receiver_hash not in (DECODED_SHA256,FAVORITES_SHA256):
        raise ValueError('Receiver does not match either independently verified source build')
    prefix,original=split_container(official)
    encoded=receiver.translate(ENCODE_TABLE)
    if encoded.translate(DECODE_TABLE)!=receiver:
        raise ValueError('Receiver encode/decode round trip failed')
    if receiver_hash==DECODED_SHA256 and encoded!=original['5680']:
        raise ValueError('Stock source build does not reproduce official receiver payload')
    if device_mstar is None:
        installed_mstar=original['8339']  # Release: no device-specific data from any one Monitor.
    else:
        # Preserve the 132 observed device filesystem bytes, rather than overwrite them with release data.
        installed_mstar=device_mstar[:len(original['8339'])]
        if any(value!=255 for value in device_mstar[len(installed_mstar):]):
            raise ValueError('Unexpected installed bytes beyond the MStar payload')
    payloads={'5680':encoded,'fpga':original['fpga'],'8339':installed_mstar}
    package=join_container(prefix,payloads)
    round_prefix,round_payloads=split_container(package)
    if round_prefix!=prefix or round_payloads!=payloads:
        raise ValueError('Update container round trip failed')
    metadata={'format':'hdzero-monitor-update-experiment-v1','flavor':'stock' if receiver_hash==DECODED_SHA256 else 'favorites',
              'official_baseline_sha256':OFFICIAL_SHA256,'receiver_decoded_sha256':receiver_hash,
              'installed_mstar_backup_sha256':DEVICE_MSTAR_SHA256 if device_mstar is not None else None,
              'mstar_source':'installed_backup' if device_mstar is not None else 'official_1.1.1',
              'container_sha256':digest(package),
              'container_bytes':len(package),'prefix_hex':prefix.hex(),'format_compatible':True,
              'device_validated':False,'ready_for_device_use':False,'hardware_access':False,
              'layout_source':SOURCE,'components':{},
              'unverified':['Device CODE loading of appended data','Device-side integrity rules',
                            'Integrated RF, persistence, display and recording behavior','Independent recovery']}
    for name,payload in payloads.items():
        metadata['components'][name]={'bytes':len(payload),'sha256':digest(payload),
                                     'pages_256':(len(payload)+255)//256,'erase_blocks_64k':(len(payload)+65535)//65536,
                                     'source':'rebuilt_receiver' if name=='5680' else 'installed_backup' if name=='8339' and device_mstar is not None else 'unchanged_official_payload'}
    metadata['preserved_mstar_release_differences']=sum(a!=b for a,b in zip(installed_mstar,original['8339']))
    return package,metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official',type=Path,required=True)
    parser.add_argument('--receiver',type=Path,required=True)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--device-mstar',type=Path,help='Preserve this installed MStar backup (personal package)')
    source.add_argument('--official-mstar',action='store_true',help='Release package: official 1.1.1 FPGA and MStar')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    package,metadata=make_package(args.official.read_bytes(),args.receiver.read_bytes(),
                                  None if args.official_mstar else args.device_mstar.read_bytes())
    args.output_dir.mkdir(parents=True,exist_ok=False)
    filename=f"HDZero_Monitor-{metadata['flavor']}-UNVALIDATED.bin"
    (args.output_dir/filename).write_bytes(package)
    (args.output_dir/'package.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':
    main()
