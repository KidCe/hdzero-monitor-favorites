"""Run only the pinned official file-parser method and simulate its flash geometry offline."""
import argparse
import ast
import json
from pathlib import Path
from types import SimpleNamespace

from monitor_update_package import split_container,digest,FAVORITES_SHA256
from monitor_receiver_decode import DECODE_TABLE,DECODED_SHA256,ARRAY_SHA256

PARSER_SOURCE_SHA256='8f52d51212fc57169e932802391c8aaaa011b3aedc6ee4b46fb892836f10d280'
BACKUPS={'5680':(1048576,ARRAY_SHA256),
         'fpga':(16777216,'a4b2b1cec69c5d042af51a439c472c127abf0c3d6f5ee9a8006956e212c6c36a'),
         '8339':(16777216,'68ffa3d3a94058e8e605a9f48179305502893c4c426706525aac4e1df5f9e887')}


def official_parser(source):
    if digest(source)!=PARSER_SOURCE_SHA256:
        raise ValueError('Official parser source differs from pinned inspected commit bytes')
    tree=ast.parse(source.decode('utf-8'))
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='ch341_class')
    method=next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name=='parse_monitor_fw')
    # Do not import/execute the module: its constructor and global objects load hardware DLLs.
    # The isolated, hash-pinned method only opens a file and reads component buffers.
    scope={}
    isolated=ast.Module(body=[method],type_ignores=[])
    exec(compile(ast.fix_missing_locations(isolated),'<pinned-official-file-parser>','exec'),scope)
    return scope['parse_monitor_fw']


def check_package(package_path,backup_directory,parser):
    raw=package_path.read_bytes()
    prefix,payloads=split_container(raw)
    if prefix!=b'\x01\x00' or digest(payloads['5680'].translate(DECODE_TABLE)) not in (DECODED_SHA256,FAVORITES_SHA256):
        raise ValueError('Unexpected package prefix or decoded receiver')
    state=SimpleNamespace()
    if parser(state,str(package_path.resolve()))!=1:
        raise ValueError('Official parser rejected package')
    for name,payload in payloads.items():
        if getattr(state,f'fw_{name}_size')!=len(payload) or getattr(state,f'fw_{name}_buf')!=payload:
            raise ValueError('Official parser disagrees with independently checked payloads')
    report={'package_sha256':digest(raw),'official_parser_accepts':True,
            'parser_dlls_or_usb_opened':False,'hardware_access':False,'device_validated':False,
            'ready_for_device_use':False,'projected_arrays':{}}
    for name,(capacity,expected_hash) in BACKUPS.items():
        original=(backup_directory/f'{name}-pass1.bin').read_bytes()
        if len(original)!=capacity or digest(original)!=expected_hash:
            raise ValueError(f'Unrecognized {name} array backup')
        payload=payloads[name]
        # Reproduce the inspected fw_write_to_flash page/block geometry in a private bytearray.
        page_count=(len(payload)+255)//256
        erase_bytes=((page_count*256+65535)//65536)*65536
        programmed=bytearray(original)
        programmed[:erase_bytes]=b'\xff'*erase_bytes
        padded=payload+b'\xff'*(page_count*256-len(payload))
        programmed[:len(padded)]=padded
        changed=sum(a!=b for a,b in zip(original,programmed))
        if name!='5680' and changed:
            raise ValueError(f'Package would alter installed {name} bytes')
        if name=='5680' and digest(payload.translate(DECODE_TABLE))==DECODED_SHA256 and changed:
            raise ValueError('Stock package would alter installed receiver bytes')
        report['projected_arrays'][name]={'array_bytes':capacity,'sha256':digest(programmed),
                                         'changed_bytes':changed,'erase_bytes':erase_bytes,
                                         'programmed_page_bytes':len(padded),'same_as_backup':programmed==original}
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--official-source',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--backups',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists():raise FileExistsError('Compatibility report must be new')
    report=check_package(args.package,args.backups,official_parser(args.official_source.read_bytes()))
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
