# LEICADISPLAYAIDS1A

Adds the handoff's two display-only aids:

- **Histogram** — a live monochrome luminance histogram measured from the rendered WYSIWYG
  viewfinder. It uses 64 bins and draws 11 visual sections, echoing the first-generation
  M Monochrom DNG review histogram. The live sections are guides, not a claim that display-coded
  preview values are raw-DNG EV zones.
- **Highlight Clipping** — Off, 100%, 99%, 98%, 97%, 96%, or 95%. Sampled rendered-viewfinder
  pixels at or above the selected luminance threshold flash red.

The original M Monochrom's clipping display is a review feature. This phone adaptation moves the
same visual idea into live view because the project requires WYSIWYG exposure aids before capture.

Implementation is display-only:
- samples the rendered TextureView at 128x96 using PixelCopy;
- neutralizes Photon's magenta focus-peaking delta before measuring;
- never writes the clipping overlay back into the preview texture;
- never changes ISO, shutter, AE, EV, JPEG render, DNG samples, tone, contrast, toning or sharpness.
