"""Opt-in conditional native-image reviewer; no fits or imports of science code on import.

This helper is untested on a new galaxy. It is NOT a validated spectra/redshift
pipeline. Call run_native_review(config) explicitly in a checked-out science
workspace. Full native 2040x2040 detector exposures are required; archive cutouts
need a separate detector-coordinate/calibration adapter and are rejected here.

Required config keys: science_repo, data_root, catalogue, exposures,
epsf_calibration, calibration_manifest, output, target. Paths are explicit local
paths; target has object_id, ra, dec (ICRS degrees at its catalogue coordinates).
exposures is a JSON list: file, release (qr2/qr3), obs_id, detector, mjd_start.
Calibration registry format: {"schema_version":1,"files":[{"path":"...",
"sha256":"64 hexadecimal characters"}]}. Relative registry paths resolve
against its parent directory. Register applicable wavelength/area/gain and
external ePSF FITS files. Hash integrity does not certify scientific applicability.

Models, masks, fit thresholds and calibration equations are imported unchanged.
Results retain conditional-noise limitations and never pass a science gate.
"""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import sys
import time

REQUIRED = {'science_repo', 'data_root', 'catalogue', 'exposures',
            'epsf_calibration', 'calibration_manifest', 'output', 'target'}
FULL_DETECTOR_SHAPE = (2040, 2040)
REQUIRED_COLUMNS = {'legacy_object_id','ra','dec','type','shape_r','shape_e1',
                    'shape_e2','sersic','pmra','pmdec','ref_epoch','maskbits','fitbits'}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def validate_config(config):
    if not isinstance(config, dict) or set(config) != REQUIRED:
        raise ValueError('Config must contain exactly: ' + ', '.join(sorted(REQUIRED)))
    target = config['target']
    if not isinstance(target, dict) or set(target) != {'object_id', 'ra', 'dec'}:
        raise ValueError('target must have exactly object_id, ra, dec; no redshift input')
    if not isinstance(target['object_id'], str) or not target['object_id'].strip():
        raise ValueError('A stable nonempty catalogue object_id is required')
    ra, dec = float(target['ra']), float(target['dec'])
    if not (math.isfinite(ra) and math.isfinite(dec) and 0 <= ra < 360 and -90 <= dec <= 90):
        raise ValueError('Target coordinates must be finite ICRS degrees')
    result = {key: str(Path(config[key]).expanduser().resolve()) for key in REQUIRED - {'target'}}
    result['target'] = dict(object_id=target['object_id'], ra=ra, dec=dec)
    for key in ['science_repo', 'data_root', 'epsf_calibration']:
        if not Path(result[key]).is_dir():
            raise ValueError(f'{key} must be an existing directory')
    for key in ['catalogue', 'exposures', 'calibration_manifest']:
        if not Path(result[key]).is_file():
            raise ValueError(f'{key} must be an existing file')
    return result


def load_exposures(path):
    path = Path(path)
    records = json.loads(path.read_text())
    if not isinstance(records, list) or not records:
        raise ValueError('Exposures must be a nonempty JSON list')
    seen = set()
    result = []
    for record in records:
        fields = {'file', 'release', 'obs_id', 'detector', 'mjd_start'}
        if not isinstance(record, dict) or not fields.issubset(record):
            raise ValueError('Each exposure requires file/release/obs_id/detector/mjd_start')
        if record['release'] not in ['qr2', 'qr3']:
            raise ValueError('Explicit qr2/qr3 release required')
        if isinstance(record['detector'], bool) or int(record['detector']) != record['detector'] or not 1 <= int(record['detector']) <= 6:
            raise ValueError('Detector must be an integer 1..6')
        identity = (str(record['obs_id']), int(record['detector']))
        if not identity[0] or identity in seen:
            raise ValueError('Duplicate/empty obs_id+detector (including across releases)')
        seen.add(identity)
        mjd = float(record['mjd_start'])
        if not math.isfinite(mjd):
            raise ValueError('Finite exposure MJD required')
        image = Path(record['file']).expanduser()
        if not image.is_absolute():
            image = path.parent / image
        image = image.resolve()
        if not image.is_file():
            raise ValueError(f'Missing native exposure: {image}')
        result.append(dict(file=str(image), release=record['release'], obs_id=identity[0],
                           detector=identity[1], mjd_start=mjd))
    return result


def verify_calibration_manifest(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('files'), list) or not manifest['files']:
        raise ValueError('Calibration manifest requires schema_version=1 and nonempty files list')
    verified = {}
    for entry in manifest['files']:
        candidate = Path(entry['path']).expanduser()
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        candidate = candidate.resolve()
        expected = entry.get('sha256', '').lower()
        if not re.fullmatch('[0-9a-f]{64}', expected) or str(candidate) in verified:
            raise ValueError('Invalid/duplicate calibration hash registry entry')
        actual = file_sha256(candidate)
        if actual != expected:
            raise ValueError(f'Calibration reference hash mismatch: {candidate}')
        verified[str(candidate)] = actual
    return verified


def angular_separation_arcsec(ra1, dec1, ra2, dec2):
    a, b, c, d = map(math.radians, [ra1, dec1, ra2, dec2])
    value = math.sin((d-b)/2)**2 + math.cos(b)*math.cos(d)*math.sin((c-a)/2)**2
    return math.degrees(2*math.asin(math.sqrt(min(1, max(0, value))))) * 3600


def validate_identity(entries, target):
    """Pure-Python identity guard; nearest-coordinate coincidence is insufficient."""
    matches = [i for i, row in enumerate(entries) if str(row['legacy_object_id']) == target['object_id']]
    if len(matches) != 1:
        raise ValueError('Target legacy_object_id must match exactly one catalogue row')
    if any(not (math.isfinite(float(row['ra'])) and math.isfinite(float(row['dec'])) and
                0 <= float(row['ra']) < 360 and -90 <= float(row['dec']) <= 90) for row in entries):
        raise ValueError('Catalogue has invalid coordinates; clean/justify its input before fitting')
    index = matches[0]
    separations = [angular_separation_arcsec(target['ra'], target['dec'], float(row['ra']), float(row['dec'])) for row in entries]
    if separations[index] >= .1:
        raise ValueError('Target ID and coordinates disagree by >=0.1 arcsec')
    if any(separation < 1 for i, separation in enumerate(separations) if i != index):
        raise ValueError('Another catalogue identity lies within 1 arcsec; review ambiguity first')
    if str(entries[index].get('type', '')).strip() == 'DUP':
        raise ValueError('Target is a catalogue DUP entry; identity review required')
    return index


def validate_stamp_position(x, y, shape=FULL_DETECTOR_SHAPE):
    if tuple(shape) != FULL_DETECTOR_SHAPE or not all(map(math.isfinite, [x, y])):
        raise ValueError('Expected a full 2040x2040 detector and finite pixel coordinates')
    ix, iy = round(x), round(y)
    if min(x, y, shape[1]-1-x, shape[0]-1-y) < 15 or ix-15 < 0 or iy-15 < 0 or ix+15 >= shape[1] or iy+15 >= shape[0]:
        raise ValueError('Target is within 15 pixels of an edge; no truncated 31x31 fit')
    return ix, iy


@contextmanager
def output_lock(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    with (output / '.native_review.lock').open('a+b') as stream:
        stream.seek(0)
        if not stream.read(1):
            stream.seek(0); stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_json(path, value):
    path = Path(path); temp = path.with_name(path.name + '.part')
    with temp.open('w', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def _require_registered(path, registry):
    path = str(Path(path).resolve())
    if path not in registry:
        raise ValueError(f'Applicable reference absent from verified manifest: {path}')
    return path


def _runtime_versions():
    versions = dict(python=sys.version, platform=platform.platform())
    for package in ['numpy', 'astropy', 'scipy', 'photutils', 'requests', 'pyvo']:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = 'not installed'
    return versions


def _existing_checkpoint(path, expected_key, np):
    if not path.exists():
        return None
    result = json.loads(path.read_text())
    arrays_path = path.with_suffix('.npz')
    if result.get('configuration_key') != expected_key or not arrays_path.is_file() or file_sha256(arrays_path) != result.get('arrays_sha256'):
        raise ValueError(f'Invalid/stale checkpoint, preserve and review before reuse: {path}')
    with np.load(arrays_path, allow_pickle=False) as arrays:
        required = {'image', 'variance', 'model', 'use', 'estimator_weights', 'native_x', 'native_y', 'native_flags'}
        if not required.issubset(arrays.files) or any(arrays[name].shape != (31,31) for name in required):
            raise ValueError(f'Checkpoint arrays incomplete or wrong shape: {arrays_path}')
        if 'configuration_key' not in arrays.files or str(arrays['configuration_key'].item()) != expected_key:
            raise ValueError(f'Checkpoint NPZ belongs to another configuration: {arrays_path}')
    return result


def run_native_review(config):
    """Execute explicitly requested conditional fits, without changing science modules.

    Returns JSON-safe result dictionaries. Existing checkpoints require matching
    content hashes and valid saved arrays. No reference redshifts are accepted.
    """
    config = validate_config(config)
    exposures = load_exposures(config['exposures'])
    registry = verify_calibration_manifest(config['calibration_manifest'])
    # Heavy dependencies and checked-out science imports occur only on explicit call.
    import numpy as np
    from astropy.table import Table
    from astropy.io import fits
    from astropy.wcs import WCS
    repo = Path(config['science_repo']); outputs = repo / 'outputs'
    code_paths = sorted(outputs.glob('*.py')) + [Path(__file__).resolve()]
    if not (outputs / 'nep_native_scene.py').is_file():
        raise ValueError('science_repo lacks outputs/nep_native_scene.py')
    code_hashes = {str(p.resolve()): file_sha256(p) for p in code_paths}
    sys.path.insert(0, str(outputs))
    import nep_native_scene
    import nep_science_calibration
    import nep_epsf_pipeline
    from nep_projected_photometry import projected_target_flux
    for module in [nep_native_scene, nep_science_calibration, nep_epsf_pipeline]:
        if Path(module.__file__).resolve().parent != outputs.resolve():
            raise ValueError('A science module is already loaded from another repository; restart kernel')
    catalogue = Table.read(config['catalogue'])
    if not REQUIRED_COLUMNS.issubset(catalogue.colnames):
        raise ValueError('Catalogue missing required columns: '+str(sorted(REQUIRED_COLUMNS-set(catalogue.colnames))))
    entries = [dict(legacy_object_id=str(row['legacy_object_id']), ra=float(row['ra']), dec=float(row['dec']), type=str(row['type'])) for row in catalogue]
    target_index = validate_identity(entries, config['target'])
    hashes = dict(catalogue=file_sha256(config['catalogue']), exposures=file_sha256(config['exposures']),
                  calibration_manifest=file_sha256(config['calibration_manifest']), references=registry, code=code_hashes)
    versions = _runtime_versions()
    results = []
    old_epsf = nep_native_scene.CALIBRATION
    with output_lock(config['output']):
        try:
            nep_native_scene.CALIBRATION = Path(config['epsf_calibration'])
            # Calibration caches must not outlive verified file-content identities.
            nep_science_calibration._reference.cache_clear(); nep_epsf_pipeline.external_epsf.cache_clear()
            for exposure in exposures:
                start = time.monotonic()
                native_hash = file_sha256(exposure['file'])
                references = {}
                with fits.open(exposure['file'], memmap=True) as hdus:
                    for extension in ['IMAGE', 'VARIANCE', 'FLAGS', 'ZODI']:
                        if hdus[extension].shape != FULL_DETECTOR_SHAPE:
                            raise ValueError('Current runner requires full native 2040x2040 IMAGE/VARIANCE/FLAGS/ZODI')
                    header = hdus['IMAGE'].header
                    if int(header['DETECTOR']) != exposure['detector'] or float(header['CRPIX1A']) != 1 or float(header['CRPIX2A']) != 1:
                        raise ValueError('Detector identity/origin incompatible with full-detector calibration')
                    if str(header.get('BUNIT','')).replace(' ','') != 'MJy/sr':
                        raise ValueError('Expected calibrated MJy/sr native image')
                    x,y = map(float, WCS(header).celestial.world_to_pixel_values(config['target']['ra'], config['target']['dec']))
                    ix,iy = validate_stamp_position(x,y)
                    raw_flags = np.array(hdus['FLAGS'].section[iy-15:iy+16,ix-15:ix+16], copy=True)
                    _, definitions = nep_epsf_pipeline.bad_mask(raw_flags, hdus['FLAGS'].header)
                    if 'EPSF' not in hdus:
                        matches = list(Path(config['epsf_calibration']).glob(f"epsf_D{exposure['detector']}_*.fits"))
                        if len(matches) != 1:
                            raise ValueError('Exactly one applicable external ePSF file required')
                        references['external_epsf'] = _require_registered(matches[0], registry)
                products = [('spectral_wcs', ['CWAVE','CBAND']), ('solid_angle_pixel_map',['IMAGE'])]
                if exposure['release'] == 'qr2':
                    products.append(('l3_flux_corrections',['IMAGE']))
                for product, extensions in products:
                    matches = list((Path(config['data_root'])/'science_calibrations/qr3'/product).glob(f"*_D{exposure['detector']}_*.fits"))
                    if len(matches) != 1:
                        raise ValueError('Exactly one applicable calibration reference required: '+product)
                    path = _require_registered(matches[0], registry); references[product] = path
                    with fits.open(path, memmap=True) as reference:
                        if any(reference[ext].shape != FULL_DETECTOR_SHAPE for ext in extensions):
                            raise ValueError('Calibration map is not a full compatible detector map')
                key = canonical_hash(dict(config=config, exposure=exposure, native_fits_sha256=native_hash,
                                          hashes=hashes, runtime_versions=versions))
                dest = Path(config['output']) / f'{key}.json'
                old = _existing_checkpoint(dest,key,np)
                if old is not None:
                    results.append(old); continue
                scene = nep_native_scene.build_native_scene(exposure,catalogue,config['target'],Path(config['data_root']))
                if any(scene[name].shape != (31,31) for name in ['signal','variance','valid','xx','yy']):
                    raise ValueError('Native stamp is truncated or inconsistent')
                if not scene['sources'] or scene['sources'][0]['legacy_id'] != config['target']['object_id']:
                    raise ValueError('Rendered target template identity disagrees with requested target')
                fit = projected_target_flux(scene['signal'],scene['variance'],scene['valid'],scene['templates'])
                values,counts = np.unique(raw_flags,return_counts=True)
                arrays_path = dest.with_suffix('.npz'); temp = arrays_path.with_name(arrays_path.name+'.part')
                with temp.open('wb') as stream:
                    np.savez_compressed(stream,configuration_key=np.asarray(key),image=scene['signal'],variance=scene['variance'],model=fit['model'],use=fit['use'],
                                        estimator_weights=fit['linear_weights'],native_x=scene['xx'],native_y=scene['yy'],native_flags=raw_flags)
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temp,arrays_path)
                result = dict(configuration_key=key, target=config['target'], matched_catalogue_row=target_index,
                    exposure=exposure,input_hashes=dict(native_fits=native_hash,**hashes),references=references,
                    runtime_versions=versions,created_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,
                    sources=scene['sources'],stamp=dict(target_pixel=[x,y],x_min=int(scene['xx'].min()),y_min=int(scene['yy'].min()),shape=[31,31]),
                    masks=dict(valid_pixels=int(np.count_nonzero(scene['valid'])),fit_pixels=int(fit['pixels']),invalid_pixels=int(np.count_nonzero(~scene['valid'])),
                               archive_flag_values=[dict(value=int(v),count=int(n)) for v,n in zip(values,counts)],flag_definitions=definitions),
                    wavelength_metadata_um=scene['wave_um'],bandwidth_metadata_um=scene['bandwidth_um'],
                    fit={name:fit[name] for name in ['flux_Jy','conditional_error_Jy','reduced_chi2','target_information_fraction','dof','nuisance_rank','unidentified_nuisance_modes']},
                    flags=['high_reduced_chi2_existing_threshold'] if fit['reduced_chi2']>3 else [],
                    arrays_sha256=file_sha256(arrays_path),science_gate_passed=False,use_for_redshift=False,
                    limitations=['Untested on a new galaxy; conditional native fits only.','No final per-exposure spectral response kernel or jointly fitted spectrum produced.',
                    'Optical shape, local ePSF, background and calibration systematic errors are not included in conditional errors.',
                    'Finite stamp and neighbour footprint may miss extended light or bright distant wings; catalogue completeness must be assessed independently.',
                    'No pixels automatically removed, no individual nuisance fluxes certified, no accepted redshift or distance.',
                    'Registry hashes certify integrity, not reference applicability; observer parallax and registration remain separate checks.'])
                # Known scientific modules emit Python scalar metadata; reject other non-JSON objects rather than dropping provenance.
                atomic_json(dest,result); results.append(result)
        finally:
            nep_native_scene.CALIBRATION = old_epsf
    return results
