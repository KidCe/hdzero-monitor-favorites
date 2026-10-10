"""Check actual reconstruction and reject source/inventory drift against independent bytes."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from monitor_receiver_source import generate_source,assemble,assembler_text,validate_inventory,DEFAULT_ASSEMBLER


class AddressingForms(unittest.TestCase):
    def test_direct_acc_and_carry_forms_remain_distinct(self):
        for text,opcode,expected in (
            ('ANL A,#0x7',0x53,'ANL 0xe0,#0x7'),
            ('ANL A,#0x7',0x54,'ANL A,#0x7'),
            ('ADD A,A',0x25,'ADD A,0xe0'),
            ('PUSH A',0xc0,'PUSH 0xe0'),
            ('CLR CY',0xc2,'CLR 0xd7'),
            ('CLR CY',0xc3,'CLR C'),
            ('JB CY,0x0123',0x20,'JB 0xd7,0x0123')):
            with self.subTest(opcode=opcode):self.assertEqual(assembler_text(text,opcode),expected)


class SourceFixtureChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'artifacts/firmware-analysis/20261009-recovered-source'
        fixture=ROOT/'artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin'
        if not fixture.exists() or not (base/'instructions.json').exists() or not DEFAULT_ASSEMBLER.exists():
            raise unittest.SkipTest('Private stock fixture, inventory or portable assembler unavailable')
        cls.stock=fixture.read_bytes()
        cls.inventory=json.loads((base/'instructions.json').read_text())
        cls.config=json.loads((ROOT/'config/favorite-channels.json').read_text())

    def test_stock_and_favorites_reassemble_byte_exactly(self):
        for favorites in (False,True):
            with self.subTest(favorites=favorites),tempfile.TemporaryDirectory() as directory:
                out=Path(directory)/'source'
                expected,metadata=generate_source(self.stock,self.inventory,out,favorites,self.config)
                result=assemble(out,DEFAULT_ASSEMBLER,expected,metadata)
                self.assertTrue(result['byte_exact_expected_match'])
                self.assertEqual(result['recovered_instruction_bytes'],48283)
                self.assertEqual((out/'receiver-rebuilt.bin').read_bytes(),expected)

    def test_changed_inventory_bytes_and_overlap_are_rejected(self):
        for field,value in (('bytes_hex','00'),('offset',3)):
            changed=copy.deepcopy(self.inventory)
            changed['instructions'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):validate_inventory(self.stock,changed)

    def test_edited_band_source_cannot_pass_with_old_expected_image(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'source'
            expected,metadata=generate_source(self.stock,self.inventory,out,True,self.config)
            constants=out/'constants.inc'
            constants.write_text(constants.read_text().replace('.define BAND_COUNT 0x7','.define BAND_COUNT 0x6'))
            with self.assertRaisesRegex(ValueError,'differ'):assemble(out,DEFAULT_ASSEMBLER,expected,metadata)
            self.assertFalse((out/'build.json').exists())

    def test_existing_success_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'source'
            expected,metadata=generate_source(self.stock,self.inventory,out,False,self.config)
            assemble(out,DEFAULT_ASSEMBLER,expected,metadata)
            saved=(out/'build.json').read_bytes()
            with self.assertRaises(FileExistsError):assemble(out,DEFAULT_ASSEMBLER,expected,metadata)
            self.assertEqual((out/'build.json').read_bytes(),saved)
