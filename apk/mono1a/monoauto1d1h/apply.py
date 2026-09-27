#!/usr/bin/env python3
"""Storage-only overlay on the assembled, validated 1G Android tree."""
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
J = root / 'app/src/main/java/com/particlesdevs/photoncamera'
writer = J / 'm9/export/MonoDngPublicWriter1B.java'
gradle = root / 'app/build.gradle'
parent = root / 'MONORECEIPTHYGIENE1A_ISOLATION.json'
if not parent.is_file() or not writer.is_file():
    raise SystemExit('MONOOUTPUT1H requires assembled 1G parent')

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def one(s, old, new, label):
    if s.count(old) != 1:
        raise SystemExit('%s anchor count=%s' % (label, s.count(old)))
    return s.replace(old, new, 1)

def inventory():
    return {str(p.relative_to(root)): digest(p) for p in sorted((root/'app/src').rglob('*')) if p.is_file()}

before = inventory()
s = original = writer.read_text()
if 'MONOOUTPUT1H_SAVELOOKUP1A' in s:
    raise SystemExit('1H already applied')
s = one(s,
    'public final class MonoDngPublicWriter1B implements MonoDngSpool1B.Publisher {\n',
    'public final class MonoDngPublicWriter1B implements MonoDngSpool1B.Publisher {\n'
    '    public static final String LOOKUP_REVISION = "MONOOUTPUT1H_SAVELOOKUP1A";\n', 'revision')
s = one(s,
'''        job.checkpoint("publicationLookupRevision",MonoSafQuery1C.REVISION,
                "publicChildQueryCount","0","publicChildRowsScanned","0","publicMetadataQueryCount","0",
                "publicLookupStrategy","fresh_projected_cursor_no_per_child_metadata_queries",
                "currentOperation","resolve_public_directory");
''',
'''        job.checkpoint("publicationLookupRevision",LOOKUP_REVISION,
                "publicChildQueryCount","0","publicChildRowsScanned","0","publicMetadataQueryCount","0",
                "publicInitialQuerySkipped","false","publicKnownUriHits","0","publicKnownUriFallbacks","0",
                "publicInitialQueryRows","0","publicInitialQueryMs","0",
                "publicConflictQueryRows","0","publicConflictQueryMs","0",
                "publicLookupStrategy","uuid_temp_first_known_uri_recovery_fresh_final_collision_scan",
                "currentOperation","resolve_public_directory");
''', 'attempt metrics')
old = '''        String name=j.output().getFileName().toString(),temporary=j.get("temporaryName");
        long n=System.nanoTime();
        // One complete query returns both exact names. Never cache a negative result.
        MonoSafQuery1C.Lookup initial=lookup(j,parent,"publicInitialQuery",name,temporary);
        j.metric("publicLookupMs",n);
        MonoSafQuery1C.Entry existing=initial.get(name),temp=initial.get(temporary);
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("existing_final_DNG_differs_private_copy_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true");return;
        }
'''
new = '''        String name=j.output().getFileName().toString(),temporary=j.get("temporaryName");
        MonoSafQuery1C.validName(name);
        MonoSafQuery1C.validName(temporary);
        if (!temporary.matches("\\\\.mono1b_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\\\.pending"))
            throw new IOException("temporary_identity_not_job_uuid");
        long n=System.nanoTime();
        // Known URIs are positive hints from this job, tied to the exact resolved parent.
        // They are reread and hash-checked, never treated as cached proof of existence.
        MonoSafQuery1C.Entry existing=known(j,parent,"publicFinalUri",name,"publicKnownFinalMetadata");
        MonoSafQuery1C.Entry temp=null;
        if(existing==null) temp=known(j,parent,"publicTemporaryUri",temporary,"publicKnownTempMetadata");
        boolean pristine=j.number("attempts",0)==1 && !"true".equals(j.get("recoveredAfterRestart"))
                && j.get("publicTemporaryUri").isEmpty() && j.get("publicFinalUri").isEmpty();
        if(existing==null && temp==null && !pristine) {
            // Older jobs, unknown URIs and ambiguous metadata retain the complete recovery lookup.
            MonoSafQuery1C.Lookup initial=lookup(j,parent,"publicInitialQuery",name,temporary);
            existing=initial.get(name);temp=initial.get(temporary);
        } else {
            // New UUID temporary: create directly. No assumption about final-name absence is made.
            // Every new rename still has the original fresh, complete collision query below.
            j.checkpoint("publicInitialQuerySkipped","true");
        }
        j.metric("publicLookupMs",n);
        j.checkpoint("publicLookupParentUri1H",parent.getUri().toString());
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("existing_final_DNG_differs_private_copy_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true","publicFilenameVerified","true");
            cleanupVerifiedTemporary(j,temp,existing);return;
        }
'''
s = one(s, old, new, 'temporary-first lookup')
old = '''        // Fresh full query before rename: do not weaken the previous conflict check for speed.
        existing=lookup(j,parent,"publicConflictQuery",name).get(name);
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("final_DNG_created_during_publication_private_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true");return;
        }
'''
new = '''        // Fresh full query before rename: do not weaken the previous conflict check for speed.
        existing=lookup(j,parent,"publicConflictQuery",name).get(name);
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("final_DNG_created_during_publication_private_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true","publicFilenameVerified","true");
            cleanupVerifiedTemporary(j,temp,existing);return;
        }
'''
s = one(s, old, new, 'matching-final cleanup')
helpers = '''    /** No path-to-document-ID construction, negative cache or provider-specific selection. */
    private MonoSafQuery1C.Entry known(MonoDngSpool1B.Job j,DocumentFile parent,
            String key,String expectedName,String metric)throws Exception {
        String value=j.get(key);
        if(value.isEmpty() || !parent.getUri().toString().equals(j.get("publicLookupParentUri1H")))return null;
        try {
            Uri uri=Uri.parse(value);
            if(!"content".equals(uri.getScheme()) || !parent.getUri().getAuthority().equals(uri.getAuthority()))
                throw new IOException("known_uri_authority_mismatch");
            MonoSafQuery1C.Entry e=metadata(j,uri,metric);
            if(!expectedName.equals(e.name))throw new IOException("known_uri_name_mismatch");
            j.checkpoint("publicKnownUriHits",Long.toString(j.number("publicKnownUriHits",0)+1));
            return e;
        } catch(SecurityException denied) {throw denied;}
        catch(IOException | IllegalArgumentException uncertain) {
            // Absence/error is NOT permission to overwrite: fall back to the full recovery query.
            j.checkpoint("publicKnownUriFallbacks",Long.toString(j.number("publicKnownUriFallbacks",0)+1),
                    "publicKnownUriFallbackReason",uncertain.getClass().getSimpleName());
            return null;
        }
    }
    /** Remove only this job's verified temporary copy after a matching final already exists. */
    private void cleanupVerifiedTemporary(MonoDngSpool1B.Job j,MonoSafQuery1C.Entry temp,
            MonoSafQuery1C.Entry finalDoc)throws Exception {
        if(temp==null || temp.id.equals(finalDoc.id) || temp.isDirectory()
                || !j.get("temporaryName").equals(temp.name))return;
        try {
            if(matches(temp.uri,j)) {
                boolean removed=DocumentsContract.deleteDocument(context.getContentResolver(),temp.uri);
                j.checkpoint("publicOwnedTemporaryRemoved",Boolean.toString(removed));
            }
        } catch(SecurityException | IOException cleanupFailure) {
            // Public final has already passed hash verification. A leftover duplicate is not lost data.
            j.checkpoint("publicOwnedTemporaryCleanupError",cleanupFailure.getClass().getSimpleName());
        }
    }
'''
s = one(s, '    private boolean matches(Uri uri,MonoDngSpool1B.Job j)throws Exception {\n',
        helpers + '    private boolean matches(Uri uri,MonoDngSpool1B.Job j)throws Exception {\n', 'known URI helpers')
# No changed copy, checksum, direct-publication or final rename implementation.
for anchor in ['    private boolean matches(Uri uri,', '    private void viaDirect(', '    private static void writeAndClose(']:
    a=original.index(anchor); b=s.index(anchor)
    if anchor.startswith('    private boolean matches'):
        end0=original.index('    private void viaDirect(',a);end1=s.index('    private void viaDirect(',b)
        assert original[a:end0]==s[b:end1]
    else:
        assert original[a:]==s[b:]
writer.write_text(s)
g=gradle.read_text(); m=re.search(r"versionName\\s+'([^']+)'",g)
# Literal regex below is intentional: Groovy parent uses single-quoted versionName.
if m is None: m=re.search(r"versionName\s+'([^']+)'",g)
if m is None: raise SystemExit('versionName missing')
g=g[:m.start(1)]+m.group(1)+'-monooutput1h-savelookup1a'+g[m.end(1):]
gradle.write_text(g)
after=inventory()
rel=str(writer.relative_to(root))
changed=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
if changed != [rel]: raise SystemExit('unexpected runtime source changes: '+repr(changed))
proof={
    'revision':'MONOOUTPUT1H_SAVELOOKUP1A','parentCommit':'b738ecc5738b0c5a7bb84b8d584c60f439d9e23e',
    'changedRuntimeFiles':changed,'writerSha256':digest(writer),
    'frozenSourceHashes':{p:h for p,h in before.items() if p!=rel},
    'frozenSourceFileCount':len(before)-1,
    'newSaveFullFolderScans':1,'previousNewSaveFullFolderScans':2,
    'freshFinalCollisionQueryRetained':True,'knownUrisRevalidated':True,'negativeCacheAdded':False,
    'opaqueDocumentIdsPreserved':True,'providerSpecificIdGuessing':False,
    'exposurePolicyChanged':False,'jpegRendererChanged':False,'dngPixelMathChanged':False,
    'diagnosticsStillEnabledForValidation':True,'diagnosticSpoolPurged':False,'dngJobDirectoryPurged':False,
    'phoneValidated':False,
}
(root/'MONOSAVELOOKUP1A_ISOLATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k!='frozenSourceHashes'},indent=2))
