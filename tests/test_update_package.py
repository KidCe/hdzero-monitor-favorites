"""Validate strict offline container geometry, payload preservation and input guards."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from monitor_update_package import split_container,join_container,make_package
from monitor_package_compatibility import official_parser,check_package


class ContainerGeometry(unittest.TestCase):
    def test_unpinned_parser_source_cannot_execute(self):
        with self.assertRaises(ValueError):official_parser(b'raise RuntimeError("must not execute")')

    def test_truncation_extra_bytes_and_size_limit_are_rejected(self):
        data=join_container(b'\x01\x00',{'5680':b'abc','fpga':b'd','8339':b'ef'})
        for changed in (data[:13],data[:-1],data+b'x'):
            with self.subTest(length=len(changed)),self.assertRaises(ValueError):split_container(changed)
        with self.assertRaises(ValueError):join_container(b'\x01\x00',{'5680':bytes(65536),'fpga':b'd','8339':b'f'})


class PackageFixtureChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/'artifacts/firmware-analysis/20261009-recovered-source'
        files=[base/'HDZero_Monitor-v1.1.1.bin',base/'stock-build-v4/receiver-rebuilt.bin',
               ROOT/'artifacts/firmware-analysis/20261010-pscan-v7/favorites-build-v7/receiver-rebuilt.bin',ROOT/'artifacts/device-backups/20261009-usb-01/8339-pass1.bin']
        if not all(path.exists() for path in files):raise unittest.SkipTest('Private source-build/package fixtures unavailable')
        cls.official,cls.stock,cls.favorites,cls.mstar=(path.read_bytes() for path in files)

    def test_original_container_and_both_packages_round_trip(self):
        prefix,original=split_container(self.official)
        self.assertEqual(join_container(prefix,original),self.official)
        for receiver in (self.stock,self.favorites):
            with self.subTest(length=len(receiver)):
                package,metadata=make_package(self.official,receiver,self.mstar)
                actual_prefix,actual=split_container(package)
                self.assertEqual(prefix,actual_prefix)
                self.assertEqual(actual['fpga'],original['fpga'])
                self.assertEqual(actual['8339'],self.mstar[:len(original['8339'])])
                self.assertEqual(metadata['preserved_mstar_release_differences'],132)
                self.assertFalse(metadata['ready_for_device_use'])

    def test_release_package_changes_only_the_receiver(self):
        package,metadata=make_package(self.official,self.favorites)
        prefix,original=split_container(self.official)
        actual_prefix,actual=split_container(package)
        self.assertEqual(actual_prefix,prefix)
        self.assertEqual(actual['fpga'],original['fpga'])
        self.assertEqual(actual['8339'],original['8339'])
        self.assertNotEqual(actual['5680'],original['5680'])
        self.assertEqual(metadata['mstar_source'],'official_1.1.1')
        self.assertIsNone(metadata['installed_mstar_backup_sha256'])
        self.assertEqual(metadata['preserved_mstar_release_differences'],0)

    def test_unrecognized_baseline_receiver_and_device_backup_are_rejected(self):
        for index in range(3):
            inputs=[self.official,self.favorites,self.mstar]
            changed=bytearray(inputs[index]);changed[-1]^=1;inputs[index]=bytes(changed)
            with self.subTest(input=index),self.assertRaises(ValueError):make_package(*inputs)

    def test_isolated_official_parser_and_array_geometry(self):
        base=ROOT/'artifacts/firmware-analysis/20261009-recovered-source'
        source=base/'programmer-ch341.py'
        if not source.exists():self.skipTest('Pinned official parser fixture unavailable')
        parse=official_parser(source.read_bytes())
        for flavor,changes in (('stock',0),('favorites',620)):
            directory=base if flavor=='stock' else ROOT/'artifacts/firmware-analysis/20261010-pscan-v7'
            package_directory='stock-package' if flavor=='stock' else 'favorites-package-v7'
            path=directory/package_directory/f'HDZero_Monitor-{flavor}-UNVALIDATED.bin'
            if not path.exists():self.skipTest('Offline package fixture unavailable')
            result=check_package(path,ROOT/'artifacts/device-backups/20261009-usb-01',parse)
            self.assertTrue(result['official_parser_accepts'])
            self.assertEqual(result['projected_arrays']['5680']['changed_bytes'],changes)
            self.assertTrue(result['projected_arrays']['8339']['same_as_backup'])
            self.assertTrue(result['projected_arrays']['fpga']['same_as_backup'])
            self.assertFalse(result['hardware_access'])
