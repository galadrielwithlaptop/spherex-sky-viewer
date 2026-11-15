# Cached rendering, comparison metadata and catalogue outages

Updated 15 November 2026.

## Hosted use

1. Open a prepared 5′ field, or click Find observations at the same coordinates.
2. Use **Refresh cached images & metadata** to pick up background preparation.
3. Choose **Watch through time**. Its wavelength selector lists groups screened
   using target-position wavelength and bandwidth, the same detector/release,
   and independent observation times. Different wavelengths are not made
   comparable simply because their source images have been downloaded.
4. In **Compare images**, choose **Choose a comparable pair**. The tab shows the
   two raw IMAGE previews, observation dates, wavelength centres and widths.
5. In **Catalogue overlays**, select a frame using **Image observation** and then
   choose Gaia or AllWISE. Playback controls also remain available in this tab.

These are metadata screening and visualization tools, not calibrated variability
measurements. Coadd, difference and mosaic products require their separate
analysis workflow; the IMAGE-only background batch does not silently create them.

## Why the earlier message appeared

The original lightweight starter frames only recorded detector-wide wavelength
bounds. They did not carry target-position wavelengths or bandwidths, so the
strict comparison correctly rejected them, but clearing the canvas was confusing.

The current display can show available images in explicitly labelled exploratory
mode when a strict time group is unavailable. Exact saved views retain their
strict selection contract. WISE0855 preparation now evaluates native WCS-WAVE
metadata; it does not estimate wavelengths from the detector-wide midpoint.

The main viewer was tested with a two-frame wavelength-screened pair separated
by about 178 days. Both images showed their target-position wavelength and
bandwidth. The first verified loaded sequence had eight independent two-frame
time groups; the count grows as the bounded background batch progresses.

## Local cache versus laptop files

`GET /api/v1/prepared` finds existing rendered raw IMAGE sequences for the
requested coordinates, diameter and detector/date filters. It performs no
archive request. It checks that the PNG files exist and returns only usable
cached frames. Ordinary search attempts this lookup before live metadata.

A public VM cannot read an arbitrary visitor's laptop filesystem. Previously
cached project cutouts were explicitly transferred from the development laptop
to this VM: 42 missing native IMAGE cutouts were added, and 59 target-wavelength
metadata records were reused. The import did not transfer or process ePSF arrays
or subtract ZODI. Future local datasets need an explicit upload/import step.

## IRSA failures

When IRSA metadata requests fail, a persistent banner says **IRSA is unavailable**.
Already cached sky images remain viewable. The AllWISE/Gaia overlay adapter
returns a structured `irsa_unavailable` error when no catalogue cache exists;
if an older catalogue exists, it returns that catalogue with a stale-data warning.
Failure of a catalogue request does not remove the selected sky frame.

The hosted AllWISE failure path was verified against an actual failed request,
alongside changing the frame with the new observation dropdown. These changes do
not repair the upstream IRSA service or establish complete archive coverage.
