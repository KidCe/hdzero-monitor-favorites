"""Build a decoded receiver from recovered 8051 assembly and explicit data bytes."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from monitor_receiver_decode import DECODED_SHA256, PAYLOAD_SIZE
from monitor_receiver_candidate import make_candidate, FLAG_BASE, INDEX_BASE, SECOND_BASE, LETTER_BASE, LABEL_IDS, LABEL_ROUTINE, SCAN_LIST_HOOK
from monitor_receiver_map import validate_config

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLER_SHA256 = 'c2e2d8b4b546d3fcdf96b6bec6341f96c3bb8095cf7a7abbaaeb044c71af1089'
DEFAULT_ASSEMBLER = Path.home() / '.cache' / 'hdzero-monitor-tools' / 'naken_asm-2024-11-03' / 'naken_asm-2024-11-03' / 'naken_asm.exe'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_inventory(stock, inventory):
    if len(stock) != PAYLOAD_SIZE or digest(stock) != DECODED_SHA256:
        raise ValueError('Only pinned decoded Monitor 1.1.1 input is supported')
    if inventory.get('format') != 'hdzero-recovered-instructions-v1' or inventory.get('image_sha256') != DECODED_SHA256:
        raise ValueError('Unexpected recovered-instruction inventory')
    end = total = 0
    rows = inventory['instructions']
    for row in rows:
        start = row['offset']
        raw = bytes.fromhex(row['bytes_hex'])
        if not raw or start < end or start + len(raw) > len(stock) or stock[start:start + len(raw)] != raw:
            raise ValueError('Invalid, overlapping or changed instruction bytes')
        if not re.fullmatch(r'[A-Z]+(?: [A-Za-z0-9_@+#/,().\-]+)?', row['assembly']):
            raise ValueError('Unexpected instruction text')
        end = start + len(raw)
        total += len(raw)
    if inventory.get('instruction_count') != len(rows) or inventory.get('instruction_bytes') != total:
        raise ValueError('Instruction coverage count mismatch')
    return rows, total


def data_lines(data, start):
    return [f'; Data / unresolved bytes at CODE:{start + offset:04X}\n  .db ' +
            ','.join(f'0x{value:02x}' for value in data[offset:offset + 16])
            for offset in range(0, len(data), 16)]


def assembler_text(text, opcode):
    # Direct ACC/PSW-bit operands can print like architectural A/C registers in Ghidra.
    # Preserve the opcode's addressing form; byte-exact assembly is the final independent check.
    parts=text.split(' ',1)
    if len(parts)==1:
        return text
    operands=parts[1].split(',')
    direct_first={0x05,0x15,0x42,0x43,0x52,0x53,0x62,0x63,0x75,0x85,0x86,0x87,0xc0,0xd0,0xd5,0xf5}
    direct_first.update(range(0x88,0x90))
    direct_second={0x25,0x35,0x45,0x55,0x65,0x85,0x95,0xa6,0xa7,0xc5,0xe5}
    direct_second.update(range(0xa8,0xb0))
    positions=([0] if opcode in direct_first else [])+([1] if opcode in direct_second else [])
    if opcode in {0x10,0x20,0x30,0x92,0xb2,0xc2,0xd2}:
        positions.append(0)
    if opcode in {0x72,0x82,0xa0,0xa2,0xb0}:
        positions.append(1)
    for index in positions:
        operands[index]=re.sub(r'\bA\b','0xe0',operands[index])
        operands[index]=re.sub(r'\bCY\b','0xd7',operands[index])
    return parts[0]+' '+','.join(re.sub(r'\bCY\b','C',operand) for operand in operands)


def generate_source(stock, inventory, output, favorites, config):
    rows, total = validate_inventory(stock, inventory)
    expected, patch_manifest = make_candidate(stock, config) if favorites else (stock, None)
    output.mkdir(parents=True, exist_ok=False)
    modules = output / 'modules'
    modules.mkdir()
    constants = {'DPL':0x82, 'DPH':0x83, 'PSW':0xd0, 'B':0xf0, 'SELECTION_STATE':0xd85,
                 'SETTINGS_SAVE':0x9f29, 'RECEIVER_REFRESH':0x61d2,
                 'BAND_COUNT':7 if favorites else 6, 'LAST_BAND':6 if favorites else 5,
                 'BAND_DOWN_ADJUST':0xf8 if favorites else 0xf9, 'SELECTION_COUNT':56 if favorites else 48,
                 'CAPABILITY_TABLE':FLAG_BASE if favorites else 0xc6c0,
                 'RF_INDEX_TABLE':INDEX_BASE if favorites else 0xc6f0,
                 'SECOND_TUNE_TABLE':SECOND_BASE if favorites else 0xef08,
                 'BAND_LETTERS':LETTER_BASE if favorites else 0xfe7,
                 'FAVORITES_LABEL_IDS':LABEL_IDS,'FAVORITES_LABEL':LABEL_ROUTINE,
                 'FAVORITES_SCAN_LIST':SCAN_LIST_HOOK}
    if favorites:
        # Scan entries 0..11 for a scan started in P: Favorites as P IDs, others unchanged.
        slot_of = {identity: 0x30 + slot for slot, identity in enumerate(validate_config(config))}
        for index, identity in enumerate((0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x19,0x2d,0x2e,0x1b)):
            constants[f'P_SCAN_{index}'] = slot_of.get(identity, identity)
    (output / 'constants.inc').write_text('\n'.join(f'.define {name} 0x{value:x}' for name, value in constants.items())+'\n')
    replacements = {}
    if favorites:
        replacements = {
            0x075b:'CJNE R6,#SELECTION_COUNT,0x075e', 0x9d4e:'CJNE R7,#SELECTION_COUNT,0x9d51',
            0x6d98:'MOV A,#0x19', 0x6d9e:'MOV A,#0x2d',
            0xb9ba:'MOV A,#0x32', 0xb9cc:'MOV DPTR,#0x100b',
            0x0951:'MOV A,#0xf4', 0x0954:'MOV A,#0x1', 0x099d:'MOV A,#0xf4', 0x09a0:'MOV A,#0x1',
            0x0c7b:'MOV DPTR,#RF_INDEX_TABLE', 0x2dbc:'MOV DPTR,#RF_INDEX_TABLE',
            0x0777:'MOV DPTR,#CAPABILITY_TABLE',
            0x5d3a:f'ADD A,#0x{SECOND_BASE & 255:x}', 0x5d3e:f'MOV A,#0x{SECOND_BASE >> 8:x}',
        }
        for low, high in ((0x600c,0x6010),(0x636a,0x636e),(0x646a,0x646e),(0x682b,0x682f)):
            replacements[low] = f'ADD A,#0x{FLAG_BASE & 255:x}'
            replacements[high] = f'ADDC A,#0x{FLAG_BASE >> 8:x}'
    # Source partitions have fixed original boundaries, not inferred C module boundaries.
    boundaries = [(0,'reset_runtime'), (0x674,'band_step'), (0x6d6,'channel_step'),
                  (0x725,'linear_and_buttons'), (0xc74,'rf_tuning'), (0x1185,'receiver_runtime'),
                  (0x5d19,'second_tune_and_modes'), (0x6426,'status_and_service'),
                  (0x6d6c,'scan_and_runtime'), (0x9d44,'settings_validate'),
                  (0x9e12,'settings_and_runtime'), (0xb576,'osd'),
                  (0xc6c0,'tables_and_runtime')]
    includes = []
    for index, (start, name) in enumerate(boundaries):
        end = boundaries[index + 1][0] if index + 1 < len(boundaries) else len(stock)
        if name in ('band_step','channel_step','settings_validate'):
            filename = f'{start:04x}_{name}.asm'
            source = (ROOT / 'firmware/receiver' / f'{name}.asm').read_text()
        else:
            filename = f'{start:04x}_{name}.asm'
            lines = [f'; Recovered address partition CODE:{start:04X}..{end:04X} (end exclusive)',f'.org 0x{start:04x}']
            pos = start
            for row in rows:
                address = row['offset']
                if not start <= address < end:
                    continue
                length = len(bytes.fromhex(row['bytes_hex']))
                if address + length > end:
                    raise ValueError('Source partition cuts an instruction')
                if address < pos:
                    continue  # Replaced label span already emitted as instructions.
                lines.extend(data_lines(stock[pos:address], pos))
                if favorites and address in (0xb7ab,0xb885):
                    lines += [f'; Seven-band label replacement at CODE:{address:04X}',
                              '  MOV DPTR,#SELECTION_STATE','  MOVX A,@DPTR',
                              '  SWAP A','  RL A','  ANL A,#0x1f',
                              '  MOV DPTR,#BAND_LETTERS','  MOVC A,@A+DPTR',
                              '  MOV DPTR,#0xfed','  MOVX @DPTR,A'] + ['  NOP'] * 6
                    pos = address + 22
                    continue
                if favorites and address == 0x6d6c:
                    # Replaces MOV DPTR,#0x816 / MOV A,#0x20; the hook performs them on the stock path.
                    lines += ['; Favorites scan-list hook at CODE:6D6C', '  LJMP FAVORITES_SCAN_LIST', '  NOP', '  NOP']
                    pos = address + 5
                    continue
                if favorites and address in (0xb87f,0xb8f8):
                    # Replaces MOV DPL,#0x15 / LJMP 0xB1DF; the trailing NOPs are never executed.
                    lines += [f'; Favorites label hook at CODE:{address:04X}',
                              '  LJMP FAVORITES_LABEL'] + ['  NOP'] * 3
                    pos = address + 6
                    continue
                text = replacements.get(address, row['assembly'])
                text = assembler_text(text, bytes.fromhex(row['bytes_hex'])[0])
                lines += [f'  {text} ; CODE:{address:04X}']
                pos = address + length
            lines.extend(data_lines(stock[pos:end], pos))
            source = '\n'.join(lines) + '\n'
        (modules / filename).write_text(source, encoding='utf-8')
        includes.append(f'.include "modules/{filename}"')
    if favorites:
        extension = '.org 0xf233\n' + '\n'.join(data_lines(expected[len(stock):LABEL_IDS], len(stock))) + '\n'
        (modules / 'f233_favorites_tables.asm').write_text(extension)
        includes.append('.include "modules/f233_favorites_tables.asm"')
        ids = '.org FAVORITES_LABEL_IDS\n' + '\n'.join(data_lines(expected[LABEL_IDS:LABEL_ROUTINE], LABEL_IDS)) + '\n'
        (modules/'favorites_label_ids.asm').write_text(ids)
        (modules/'favorites_label.asm').write_text((ROOT/'firmware/receiver/favorites_label.asm').read_text())
        includes += ['.include "modules/favorites_label_ids.asm"', '.include "modules/favorites_label.asm"']
        (modules/'favorites_scan_list.asm').write_text((ROOT/'firmware/receiver/favorites_scan_list.asm').read_text())
        includes.append('.include "modules/favorites_scan_list.asm"')
    master = '; Recovered receiver assembly. AI assistance is documented in the project README.\n.8051\n.include "constants.inc"\n'
    (output / 'receiver.asm').write_text(master + '\n'.join(includes) + '\n')
    source_hashes = {str(p.relative_to(output)).replace('\\','/'):digest(p.read_bytes())
                     for p in sorted(output.rglob('*')) if p.is_file()}
    metadata = {'format':'hdzero-receiver-source-build-v1','stock_sha256':DECODED_SHA256,
                'flavor':'favorites' if favorites else 'stock','expected_sha256':digest(expected),
                'instruction_count':len(rows),'recovered_instruction_bytes':total,
                'original_data_or_unresolved_bytes':len(stock)-total,
                'original_instruction_coverage_percent':round(100*total/len(stock),3),
                'source_files_sha256':source_hashes,'hardware_access':False,
                'device_validated':False,'semantic_limits':'Recovered assembly, not original C; opaque data and unresolved bytes retained explicitly'}
    if patch_manifest:
        metadata['candidate_manifest'] = patch_manifest
    return expected, metadata


def assemble(output, assembler, expected, metadata):
    if digest(assembler.read_bytes()) != ASSEMBLER_SHA256:
        raise ValueError('Assembler executable does not match the inspected portable build')
    binary = output / 'receiver-rebuilt.bin'
    if binary.exists() or (output/'build.json').exists():
        raise FileExistsError('Build outputs must be new; stale success metadata must not survive a failed rebuild')
    result = subprocess.run([str(assembler.resolve()),'-q','-type','bin','-o',binary.name,'receiver.asm'],
                            cwd=output, capture_output=True, text=True, timeout=120)
    (output / 'assembler.log').write_text(result.stdout + result.stderr)
    if result.returncode or not binary.exists():
        raise RuntimeError('Assembler failed; inspect assembler.log')
    actual = binary.read_bytes()
    if actual != expected:
        mismatch = next((i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b),min(len(actual),len(expected)))
        raise ValueError(f'Rebuilt bytes differ from independent expected image at {mismatch:#x}; lengths {len(actual)}/{len(expected)}')
    metadata.update({'assembler_sha256':ASSEMBLER_SHA256,'rebuilt_sha256':digest(actual),
                     'rebuilt_bytes':len(actual),'byte_exact_expected_match':True})
    (output / 'build.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--flavor',choices=('stock','favorites'),default='stock')
    parser.add_argument('--config',type=Path,default=ROOT/'config/favorite-channels.json')
    parser.add_argument('--assembler',type=Path,default=DEFAULT_ASSEMBLER)
    args=parser.parse_args()
    expected,metadata=generate_source(args.stock.read_bytes(),json.loads(args.inventory.read_text()),
                                     args.output_dir,args.flavor=='favorites',json.loads(args.config.read_text()))
    result=assemble(args.output_dir,args.assembler,expected,metadata)
    print(json.dumps({key:result[key] for key in ('flavor','rebuilt_sha256','rebuilt_bytes',
                     'byte_exact_expected_match','recovered_instruction_bytes','original_instruction_coverage_percent')},indent=2))


if __name__=='__main__':
    main()
