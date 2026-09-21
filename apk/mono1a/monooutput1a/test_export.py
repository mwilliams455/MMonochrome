#!/usr/bin/env python3
"""Independent file readers on synthetic fixtures. No device/Lightroom parity claim."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile
import numpy as np
import tifffile
import rawpy
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
out=root/'monooutput1a-fixtures';out.mkdir(exist_ok=True)
java=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/export'
with tempfile.TemporaryDirectory() as d:
    subprocess.run(['javac','-d',d,str(java/'MonoLinearPlane1A.java'),str(java/'MonoDngWriter1A.java'),str(here/'MonoDngHostTest.java')],check=True)
    subprocess.run(['java','-Xmx512m','-cp',d,'MonoDngHostTest',str(out)],check=True)
fixtures=json.loads((out/'fixtures.json').read_text());results=[]
for fixture in fixtures['fixtures']:
    path=out/fixture['file'];expected=np.fromfile(path.with_suffix('.u16'),dtype='<u2').reshape(fixture['height'],fixture['width'])
    item={'file':path.name,'synthetic':True,'width':fixture['width'],'height':fixture['height']}
    with tifffile.TiffFile(path) as tf:
        main=tf.pages[0];raw=main.pages[0];pixels=raw.asarray()
        assert np.array_equal(pixels,expected),path.name
        assert raw.photometric==34892 and raw.bitspersample==16 and raw.samplesperpixel==1
        assert raw.tags[50717].value==65535 and raw.tags[50714].value==(0,1)
        assert main.tags[274].value==1
        assert 33421 not in raw.tags and 33422 not in raw.tags
        assert 50721 not in raw.tags and 50721 not in main.tags
        ev=main.tags[50730].value
        assert abs(ev[0]/ev[1]-np.log2(fixture['sourceUnitsPerWhite']))<=.50001e-6
        assert main.tags[50827].value=='synthetic-original.dng'
        thumb=main.asarray();assert np.array_equal(thumb[:,:,0],thumb[:,:,1]) and np.array_equal(thumb[:,:,0],thumb[:,:,2])
        item['tiffAllSamplesExact']=True;item['samples']=int(pixels.size)
    # LibRaw rejects tiny camera frames by design; test realistic frame sizes, not 1x1 fixtures.
    if min(fixture['width'],fixture['height'])>=128:
        with rawpy.imread(str(path)) as raw:
            a=raw.raw_image_visible.copy();item['librawNumColors']=raw.num_colors
            assert np.array_equal(a,expected),(path.name,a.shape,expected.shape)
            # rawpy represents a flat monochrome sensor as a 1x1 pattern;
            # LibRaw COLOR returns sentinel 6 when filters==0; None means stacked RGB.
            pattern=raw.raw_pattern
            item['rawpyMonochromePattern']=None if pattern is None else pattern.tolist()
            print('LIBRAW_METADATA',path.name,item,flush=True)
            assert raw.num_colors==1 and pattern is not None and pattern.shape==(1,1) and int(pattern[0,0])==6
            rgb=raw.postprocess(gamma=(1,1),no_auto_bright=True,output_bps=16,user_flip=0)
            item['librawDevelopedShape']=list(rgb.shape)
            assert rgb.shape[:2]==(fixture['height'],fixture['width']) and rgb.ndim==3 and rgb.shape[2] in (1,3),rgb.shape
            # Depending on LibRaw output options, monochrome output is one plane
            # or three identical planes. Do not modify/override the input colour count.
            if rgb.shape[2]==3:
                assert np.array_equal(rgb[:,:,0],rgb[:,:,1]) and np.array_equal(rgb[:,:,0],rgb[:,:,2])
            assert rgb.dtype==np.uint16 and np.ptp(rgb)>0
            item['librawAllSamplesExact']=True;item['librawDevelopsMonochrome']=True
    else:item['librawStatus']='tiny_fixture_not_camera_sized'
    # ExifTool validation is independent of the TIFF reader and retained verbatim.
    run=subprocess.run(['exiftool','-validate','-warning','-error','-a',str(path)],capture_output=True,text=True,check=True)
    item['exiftool']=run.stdout.strip();assert 'Error' not in run.stdout,run.stdout
    results.append(item)
proof=json.loads((root/'MONOOUTPUT1A_ISOLATION.json').read_text())
for rel,h in proof['frozenFiles'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel
report={'status':'PASS','fixtureCount':len(results),'hostAssertions':fixtures['hostAssertions'],
        'independentReaders':{'tifffile':tifffile.__version__,'rawpy':rawpy.__version__,'LibRaw':rawpy.libraw_version},
        'results':results,'isolation':proof,'phoneExportValidated':False,'LightroomValidated':False}
(root/'MONOOUTPUT1A_EXPORT_TEST.json').write_text(json.dumps(report,indent=2)+'\n')
print('MONOOUTPUT1A independent TIFF, LibRaw, ExifTool and frozen-input checks PASS')
print(json.dumps(report,indent=2))
