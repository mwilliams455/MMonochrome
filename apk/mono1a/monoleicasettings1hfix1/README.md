# LEICABRACKET1B_ADMISSIONFIX1

Phone test of LEICABRACKET1A produced exactly the reported failure: only the first JPEG + DNG
pair appeared from a 3-frame sequence.

Root cause: frame 1's JPEG processing completion occurred before the durable monochrome-DNG
publisher reopened its capture-admission gate. LEICABRACKET1A used a fixed 120 ms delay and
called `takePicture()` for frame 2 too early. The existing MONOOUTPUT1B admission guard rejected
that capture, leaving no later callback to advance the series.

Fix:
- do not mark an internal bracket frame as awaiting completion until DNG admission has passed;
- replace the 120 ms continuation with a non-notifying cached admission poll;
- submit the next physical exposure only when the DNG exporter can accept it;
- retain a bounded 20 second timeout;
- no HDR merge or stacking changes;
- JPEG renderer and DNG pixel math remain frozen.

Expected output for 3-frame JPEG+RAW: **3 JPEGs + 3 derived monochrome DNGs**.
