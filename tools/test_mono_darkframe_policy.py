#!/usr/bin/env python3
import importlib.util,pathlib
p=pathlib.Path(__file__).with_name("mono_darkframe_policy.py")
spec=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

# ISO code/bucket mapping for the first-gen Monochrom normal menu.
assert m.iso_bucket(320)==0
assert m.iso_bucket(1000)==0
assert m.iso_bucket(1250)==1
assert m.iso_bucket(4000)==1
assert m.iso_bucket(5000)==2
assert m.iso_bucket(10000)==2

# Temperature group boundaries recovered from the normal control path.
assert m.temperature_group(19)==1
assert m.temperature_group(20)==2
assert m.temperature_group(39)==2
assert m.temperature_group(40)==3

# Effective thresholds for normal M Monochrom ISO range.
assert m.threshold_us(320,10)==500_000
assert m.threshold_us(1250,10)==250_000
assert m.threshold_us(5000,10)==66_000
assert m.threshold_us(320,25)==250_000
assert m.threshold_us(1250,25)==125_000
assert m.threshold_us(5000,25)==66_000
assert m.threshold_us(320,45)==66_000
assert m.threshold_us(1250,45)==33_300
assert m.threshold_us(5000,45)==16_600

# Firmware comparison is strict and quantized by /10.
assert not m.needs_black_ref(320,250_000,25)
assert m.needs_black_ref(320,250_010,25)
assert not m.needs_black_ref(1250,33_300,45)
assert m.needs_black_ref(1250,33_310,45)

print("MONO_DARKFRAME1A_POLICY_TEST PASS")
