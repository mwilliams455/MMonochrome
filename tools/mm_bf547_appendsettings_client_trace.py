#!/usr/bin/env python3
"""Close the BF547 client-side producer for SportNet command 0x04 / 37-byte AppendSettings.

This is a narrow follow-up to mm_bf547_sportnet_client_probe.py.  It does not
promote constant proximity as semantics.  Instead it emits derived BF547
control/data-flow evidence around the two strong Monochrom candidates already
seen in canonical 1.022:

  0x696b4  generic request/transport helper candidate
  0x6ceb4  wrapper that materializes selector 4 and payload size 0x25
  0x6cf24  direct caller that constructs a 37-byte local record

It also traces the BF547 diagnostic strings around Processing-Settings / nNoise
and every direct invocation of 0x696b4 that loads R1=4 and R2=0x25 nearby.
No firmware bytes are published; output is disassembly-derived evidence only.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402

RAM = 0x20000
ADDR_RE = re.compile(r'^\s*([0-9a-fA-F]+):')
CALL_RE = re.compile(r'\bCALL\s+(?:0x0x|0x)?([0-9a-fA-F]+)', re.I)

TARGETS = {
    'sportnet_transport_candidate': 0x696b4,
    'appendsettings_wrapper_candidate': 0x6ceb4,
    'appendsettings_local_builder_candidate': 0x6cf24,
}
STRINGS = {
    'processing_settings_marker_warning': 0xed9d4,
    'settings_label': 0xeda08,
    'nNoise_label': 0xedae0,
    'noise_stage_label': 0xee344,
    'sharp_stage_label': 0xee34c,
    'processing_settings_table_header': 0xee834,
    'sharpness_settings_table_row': 0xeea34,
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def component(root: bytes) -> bytes:
    hits = []
    def rec(d: bytes, depth: int = 0):
        if depth > 4 or d[:4] != b'PWAD':
            return
        for x in pwad.parse_pwad(d):
            if x.name.upper() == 'BF547':
                hits.append(x.data)
            if x.data[:4] == b'PWAD':
                rec(x.data, depth + 1)
    rec(root)
    if len(hits) != 1:
        raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]


def disasm(objdump: pathlib.Path, b: bytes, work: pathlib.Path) -> list[str]:
    p = work / 'mm_bf547.bin'
    p.write_bytes(b)
    r = subprocess.run(
        [str(objdump), '-D', '-b', 'binary', '-m', 'bfin', f'--adjust-vma={RAM:#x}', str(p)],
        capture_output=True, text=True, check=True,
    )
    p.unlink()
    return r.stdout.splitlines()


def ao(line: str) -> int:
    m = ADDR_RE.match(line)
    return int(m.group(1), 16) if m else -1


def addr_index(lines: list[str]) -> dict[int, int]:
    out = {}
    for i, l in enumerate(lines):
        a = ao(l)
        if a >= 0:
            out[a] = i
    return out


def around(lines: list[str], amap: dict[int, int], addr: int, before: int = 80, after: int = 180) -> list[str]:
    # nearest instruction at/after addr if exact address is not an instruction boundary
    if addr in amap:
        i = amap[addr]
    else:
        candidates = [(abs(a - addr), i) for a, i in amap.items() if abs(a - addr) <= 16]
        if not candidates:
            return []
        i = min(candidates)[1]
    return lines[max(0, i-before):min(len(lines), i+after)]


def direct_callers(lines: list[str], target: int, before: int = 45, after: int = 35) -> list[dict]:
    out = []
    for i, l in enumerate(lines):
        m = CALL_RE.search(l)
        if m and int(m.group(1), 16) == target:
            out.append({'site': hex(ao(l)), 'context': lines[max(0, i-before):min(len(lines), i+after)]})
    return out


def split_refs(lines: list[str], target: int) -> list[dict]:
    high = (target >> 16) & 0xffff
    low = target & 0xffff
    hi_re = re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{high:x}\b', re.I)
    lo_re = re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{low:x}\b', re.I)
    out = []
    for i, l in enumerate(lines):
        h = hi_re.search(l); lo = lo_re.search(l)
        if not (h or lo):
            continue
        reg = (h or lo).group(1).upper()
        for j in range(i+1, min(len(lines), i+20)):
            other = lo_re.search(lines[j]) if h else hi_re.search(lines[j])
            if other and other.group(1).upper() == reg:
                ctx = lines[max(0, i-30):min(len(lines), j+55)]
                out.append({
                    'first_site': hex(ao(l)),
                    'second_site': hex(ao(lines[j])),
                    'register': reg,
                    'indirect_transfers': [x for x in ctx if re.search(rf'\b(?:CALL|JUMP)\s*\(\s*{reg}\s*\)', x, re.I)],
                    'context': ctx,
                })
                break
    return out


def literal_u32_hits(bf: bytes, target: int) -> list[str]:
    needle = struct.pack('<I', target)
    out = []
    p = 0
    while True:
        p = bf.find(needle, p)
        if p < 0:
            break
        out.append(hex(RAM + p)); p += 1
    return out


def command04_transport_calls(lines: list[str], transport: int) -> list[dict]:
    """Find calls to transport with explicit R1=4 and R2=0x25 in prior ~24 instructions."""
    out = []
    for i, l in enumerate(lines):
        m = CALL_RE.search(l)
        if not (m and int(m.group(1), 16) == transport):
            continue
        lo = max(0, i-34)
        pre = lines[lo:i]
        has4 = any(re.search(r'\bR1\s*=\s*0x4\b', x, re.I) or re.search(r'\bR1\s*=\s*4\b', x, re.I) for x in pre)
        has25 = any(re.search(r'\bR2\s*=\s*0x25\b', x, re.I) or re.search(r'\bR2\s*=\s*37\b', x, re.I) for x in pre)
        if has4 and has25:
            ctx = lines[max(0, i-70):min(len(lines), i+70)]
            out.append({
                'call_site': hex(ao(l)),
                'stack_arg_stores': [x for x in ctx if re.search(r'\[(?:SP|FP)[^\]]*\]\s*=|\[SP\s*\+', x, re.I)],
                'context': ctx,
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mm_decrypted', type=pathlib.Path)
    ap.add_argument('--objdump', type=pathlib.Path, required=True)
    ap.add_argument('--outdir', type=pathlib.Path, required=True)
    a = ap.parse_args()

    mm = a.mm_decrypted.read_bytes()
    if sha(mm) != MM_DEC_SHA:
        raise SystemExit('MM decrypted SHA mismatch')
    bf = component(mm)
    a.outdir.mkdir(parents=True, exist_ok=True)
    work = a.outdir / '_work'; work.mkdir(exist_ok=True)
    lines = disasm(a.objdump, bf, work)
    amap = addr_index(lines)
    for p in work.iterdir(): p.unlink()
    work.rmdir()

    targets = {}
    for name, target in TARGETS.items():
        targets[name] = {
            'target': hex(target),
            'window': around(lines, amap, target),
            'direct_callers': direct_callers(lines, target),
            'literal_u32_hits': literal_u32_hits(bf, target),
            'split_immediate_hits': split_refs(lines, target),
        }

    strings = {}
    for name, target in STRINGS.items():
        strings[name] = {
            'target': hex(target),
            'literal_u32_hits': literal_u32_hits(bf, target),
            'split_immediate_hits': split_refs(lines, target),
        }

    command_calls = command04_transport_calls(lines, TARGETS['sportnet_transport_candidate'])
    report = {
        'schema': 'mmonochrom.bf547.appendsettings-client-trace1a.v1',
        'bf547_sha256': sha(bf),
        'known_server_contract': {'selector': 4, 'payload_bytes': 37},
        'targets': targets,
        'processing_string_xrefs': strings,
        'selector4_len37_transport_calls': command_calls,
        'classification': 'dataflow_evidence_not_final_process_mask',
        'guardrails': [
            'A selector-4/length-37 transport call strongly identifies command shape but does not alone prove which caller is normal still/JPEG processing.',
            'Do not infer the process-mask value until the 37-byte payload pointer is traced to its producer and first u32.',
            'Do not change RAWSCALAR1B or Android sharpness from this probe alone.',
        ],
    }
    jp = a.outdir / 'MM_BF547_APPENDSETTINGS_CLIENT_TRACE.json'
    tp = a.outdir / 'MM_BF547_APPENDSETTINGS_CLIENT_TRACE.txt'
    jp.write_text(json.dumps(report, indent=2) + '\n')
    with tp.open('w') as f:
        f.write(json.dumps({
            'schema': report['schema'],
            'bf547_sha256': report['bf547_sha256'],
            'selector4_len37_transport_calls': [x['call_site'] for x in command_calls],
            'target_direct_caller_counts': {k: len(v['direct_callers']) for k,v in targets.items()},
            'string_split_xref_counts': {k: len(v['split_immediate_hits']) for k,v in strings.items()},
        }, indent=2) + '\n')
        for name, d in targets.items():
            f.write(f'\n===== TARGET {name} {d["target"]} =====\n')
            f.write('\n-- FUNCTION WINDOW --\n' + '\n'.join(d['window']) + '\n')
            f.write('\n-- DIRECT CALLERS --\n' + json.dumps(d['direct_callers'], indent=2) + '\n')
            f.write('\n-- SPLIT/LITERAL XREFS --\n' + json.dumps({'literal_u32_hits':d['literal_u32_hits'],'split_immediate_hits':d['split_immediate_hits']}, indent=2) + '\n')
        f.write('\n===== COMMAND 0x04 / 0x25 TRANSPORT CALLS =====\n' + json.dumps(command_calls, indent=2) + '\n')
        f.write('\n===== PROCESSING STRING XREFS =====\n' + json.dumps(strings, indent=2) + '\n')
    print(json.dumps({
        'command04_len37_calls': [x['call_site'] for x in command_calls],
        'direct_callers': {k: len(v['direct_callers']) for k,v in targets.items()},
        'processing_string_split_xrefs': {k: len(v['split_immediate_hits']) for k,v in strings.items()},
    }, indent=2))

if __name__ == '__main__':
    main()
