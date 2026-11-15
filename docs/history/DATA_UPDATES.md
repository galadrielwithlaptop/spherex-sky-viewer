# Updating hosted image data without redeploying the website

The hosted starter page is https://srv2163798.hstgr.cloud/starter.html.
It reads /products/starter/index.json with cache disabled every ten seconds.
Its HTML is independent of the number of records and image product IDs.

## Persistent locations on the VM

- Website and backend source: /opt/spherex/app (built into the Docker image).
- Persistent data: /opt/spherex/data, mounted as /data in the container.
- Metadata database: /opt/spherex/data/catalogue.sqlite.
- Image products: /opt/spherex/data/products/PRODUCT_ID/.
- Published starter catalogue: /opt/spherex/data/products/starter/index.json.
- Batch report: /opt/spherex/data/starter-5arcmin.json.

The published JSON drives the starter page. The SQLite database drives coordinate
searches in the full viewer. They serve different purposes: adding an image to
the starter JSON does not add an archive observation to the searchable index.

## Adding an image to an existing target

1. Finish writing its FITS/PNG files under the persistent products directory.
2. Add its observation metadata to that target's selected array: id,
   time_start_utc, detector, wavelength_bounds_um, and source provenance.
3. Add a matching results entry containing id, state="ready", image (the public
   PNG path) and native_fits (the public downloadable FITS path).
4. Write the updated JSON to index.next.json, validate it, then atomically rename
   it to index.json. Never publish ready entries before their files exist.
5. The page picks it up on its next refresh. No image rebuild, container restart
   or website deployment is needed.

For example, a new result can point to:

    {"id":"<observation ID>","state":"ready",
     "image":"/products/<product ID>/raw/0.png",
     "native_fits":"/products/<product ID>/native-image.fits"}

Keep the selected record with the same ID. Do not invent an observation ID,
coverage claim, date, wavelength range or prepared count. The page derives ready
counts from actual results; indexed_matches refers to archive metadata only.

## Moving or removing files

Keep the public paths stable whenever possible. To move an image, copy it to its
new location first, verify the new URL, publish metadata with the new path, then
remove the old copy after existing clients have refreshed. Update native_fits
as well if that file moves. External HTTPS image URLs can also be recorded, but
their availability and access policy must allow the browser to display them.

To remove an image, remove its ready result from the published catalogue before
deleting its files. A path change without a metadata update creates broken links;
the application cannot infer where someone moved a file.

Do not move the host data directory without updating the Docker volume mount.
Archive metadata and previously generated products are not automatically updated
by one another. A metadata refresh never creates missing science pixels or PNGs.

## Current starter scope

Three observations for each of five 5-arcminute fields. Native IMAGE extraction,
nearest-pixel sky alignment and display stretching only. No ePSF, no ZODI
subtraction, no quality-flag masking. Images can contain artifacts and different
wavelengths. The starter gallery currently uses a separate stretch for each image;
it is not calibrated variability photometry or a confirmed source detection.

The full viewer and its archive APIs are deployed too, but this small starter
batch does not establish all-sky completeness or validate every advanced feature.
