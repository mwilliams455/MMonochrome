#!/usr/bin/env python3
"""Receipt recovery/diagnostic storage only; retain unfinished photographic jobs."""
from pathlib import Path
import hashlib
import json
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
main = root / 'app/src/main'
java = main / 'java/com/particlesdevs/photoncamera'
store = java / 'm9/export/MonoDngSpool1B.java'
spool = java / 'm9/M9DiagnosticBurstSpool.java'
gradle = root / 'app/build.gradle'
for p in (store, spool, gradle):
    if not p.is_file():
        raise SystemExit('RECEIPTHYGIENE1A missing prerequisite: ' + str(p))

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def one(s, old, new, label):
    if s.count(old) != 1:
        raise SystemExit(label + ' anchor count=' + str(s.count(old)))
    return s.replace(old, new, 1)

s, d, g = store.read_text(), spool.read_text(), gradle.read_text()
if 'MMONOSPOOLRESET1A_ONCE' not in d:
    raise SystemExit('RECEIPTHYGIENE1A requires generated SPOOLRESET1A parent')
if 'MONOOUTPUT1G_RECEIPTHYGIENE1A' in s:
    raise SystemExit('RECEIPTHYGIENE1A already applied')
# Hash all source/assets, not just a hand-selected subset. Only these two
# diagnostic/storage classes may differ; Gradle receives a version suffix.
frozen = {str(p.relative_to(root)): digest(p) for p in main.rglob('*')
          if p.is_file() and p not in (store, spool)}
before_store, before_spool = digest(store), digest(spool)

s = one(s, '    public static final String REVISION="MONOOUTPUT1B_DURABLE_EXPORT";\n',
'''    public static final String REVISION="MONOOUTPUT1B_DURABLE_EXPORT";
    public static final String RECOVERY_REVISION="MONOOUTPUT1G_RECEIPTHYGIENE1A";
    private static final java.util.concurrent.atomic.AtomicLong SUPPRESSED_RECOVERY_RECEIPTS_1G =
            new java.util.concurrent.atomic.AtomicLong();
    private static final java.util.concurrent.atomic.AtomicLong REPORTED_RECOVERY_RECORDS_1G =
            new java.util.concurrent.atomic.AtomicLong();
    public static long suppressedRecoveryReceipts1G(){return SUPPRESSED_RECOVERY_RECEIPTS_1G.get();}
    public static long reportedRecoveryRecords1G(){return REPORTED_RECOVERY_RECORDS_1G.get();}
''', 'recovery telemetry')
s = one(s,
'''        // Diagnostic replay only: no public image I/O while recovering the private store.
        for(Job j:ordered())emit(j,true);
''',
'''        // RECEIPTHYGIENE1A: keep completed receipts for idempotence, but do not
        // recreate an already-acknowledged diagnostic on every process restart.
        // Pending/failed/unacknowledged records still get the original replay.
        for(Job j:ordered()) {
            if(acknowledgedCompletion1G(j)) {
                SUPPRESSED_RECOVERY_RECEIPTS_1G.incrementAndGet();
            } else {
                emit(j,true);
                REPORTED_RECOVERY_RECORDS_1G.incrementAndGet();
            }
        }
''', 'recovery replay')
s = one(s, '    private void emit(Job j,boolean force) {\n',
'''    private boolean acknowledgedCompletion1G(Job j) {
        synchronized(j.p) {
            long seq=j.number("statusSequence",-1);
            return "exported".equals(j.get("status"))
                    && "true".equals(j.get("publicWriteCompleted"))
                    && "true".equals(j.get("publicReadbackVerified"))
                    && "true".equals(j.get("privatePayloadReleased"))
                    && seq>0 && j.number("reportedSequence",-1)>=seq;
        }
    }
    private void emit(Job j,boolean force) {
''', 'acknowledged terminal predicate')

# The old one-time purge already ran on deployed phones. A distinct marker
# clears the private diagnostic copies recreated by the old receipt producer.
# No DNG job directory, payload, receipt, DCIM file, or preference is purged here.
d = one(d, '"MMONOSPOOLRESET1A_ONCE"', '"MMONOSPOOLRESET1B_ONCE"', 'reset revision')
d = one(d, '"mmonochrome_diag_spool_reset1a.done"',
        '"mmonochrome_diag_spool_reset1b.done"', 'reset marker')
d = one(d, '            o.put("monoSpoolResetRevision", MONO_SPOOL_RESET_REVISION);\n',
'''            o.put("monoDngReceiptRecoveryRevision",
                    com.particlesdevs.photoncamera.m9.export.MonoDngSpool1B.RECOVERY_REVISION);
            o.put("monoDngRecoveryCompletedReceiptsSuppressed",
                    com.particlesdevs.photoncamera.m9.export.MonoDngSpool1B.suppressedRecoveryReceipts1G());
            o.put("monoDngRecoveryOtherRecordsReplayed",
                    com.particlesdevs.photoncamera.m9.export.MonoDngSpool1B.reportedRecoveryRecords1G());
            o.put("monoSpoolResetRevision", MONO_SPOOL_RESET_REVISION);
''', 'receipt telemetry in burst')
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit('versionName missing')
g = g[:m.end(1)] + '-monoauto1d1g-receipthygiene1a' + g[m.end(1):]
store.write_text(s)
spool.write_text(d)
gradle.write_text(g)
for rel, expected in frozen.items():
    if digest(root / rel) != expected:
        raise SystemExit('Frozen source changed: ' + rel)
proof = {
    'revision': 'MONOOUTPUT1G_RECEIPTHYGIENE1A',
    'parent': 'MMONOSPOOLRESET1A_ONCE',
    'behavior': 'skip_only_acknowledged_verified_exported_receipt_replay',
    'completedReceiptsRetainedForIdempotence': True,
    'unfinishedDngRecoveryPreserved': True,
    'unacknowledgedCompletionReplayPreserved': True,
    'failureAndConflictReplayPreserved': True,
    'privateDiagnosticReset': 'MMONOSPOOLRESET1B_ONCE',
    'resetScope': 'filesDir/m9diag_spool_only',
    'dngJobDirectoryPurged': False,
    'publicFilesDeleted': False,
    'photographicSourceFilesChanged': False,
    'exposurePolicyChanged': False,
    'frozenSourceFileCount': len(frozen),
    'frozenSourceHashes': frozen,
    'changedStorageSources': {
        str(store.relative_to(root)): {'before': before_store, 'after': digest(store)},
        str(spool.relative_to(root)): {'before': before_spool, 'after': digest(spool)}
    }
}
(root / 'MONORECEIPTHYGIENE1A_ISOLATION.json').write_text(json.dumps(proof, indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='frozenSourceHashes'}, indent=2))
