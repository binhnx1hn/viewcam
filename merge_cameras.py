"""
merge_cameras.py
----------------
Merges camera data from:
  - Movis_import_cameras_C11 (1).csv  (camera list with cameraCode, name, url)
  - go2rtc.yaml                        (stream definitions with _origin, _people keys)

Join key: IP address extracted from the RTSP URL in both sources.

Output: camera_streams_map.csv
"""

import csv
import re
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_ip(url: str) -> str | None:
    """Extract IPv4 address from an RTSP URL string."""
    if not url:
        return None
    # Match IP in URL like rtsp://user:pass@192.168.x.x:port/...
    match = re.search(r'@([\d.]+):', url)
    if match:
        return match.group(1)
    # Fallback: match bare IP (e.g. rtsp://192.168.x.x:port/...)
    match = re.search(r'rtsp://([\d.]+):', url)
    if match:
        return match.group(1)
    return None


def normalize_url(url: str) -> str:
    """Normalize %25 → % so YAML and CSV URLs compare equally (not needed for
    IP extraction, but useful for display)."""
    return url.replace('%25', '%')


# ---------------------------------------------------------------------------
# Step 1: Parse CSV
# ---------------------------------------------------------------------------

CSV_FILE = 'Movis_import_cameras_C11 (1).csv'

csv_cameras: list[dict] = []

with open(CSV_FILE, encoding='utf-8-sig', newline='') as fh:
    reader = csv.DictReader(fh)
    for row in reader:
        code = row.get('cameraCode', '').strip()
        name = row.get('name', '').strip()
        url  = row.get('url', '').strip()
        # Skip empty rows (trailing blank lines in the CSV)
        if not code and not url:
            continue
        ip = extract_ip(url)
        csv_cameras.append({
            'cameraCode': code,
            'name': name,
            'url': url,
            'ip': ip,
        })

print(f"[CSV] Loaded {len(csv_cameras)} camera rows")

# Build IP → camera lookup (CSV)
ip_to_csv: dict[str, dict] = {}
for cam in csv_cameras:
    if cam['ip']:
        ip_to_csv[cam['ip']] = cam


# ---------------------------------------------------------------------------
# Step 2: Parse YAML
# ---------------------------------------------------------------------------

YAML_FILE = 'go2rtc.yaml'

with open(YAML_FILE, encoding='utf-8') as fh:
    yaml_data = yaml.safe_load(fh)

streams: dict = yaml_data.get('streams', {})

# Collect _origin entries
# Each value is a list; first entry is the camera RTSP, rest are bbox URLs.
origins: dict[str, dict] = {}   # origin_id → {origin_url, bbox_streams}

for key, value in streams.items():
    if not key.endswith('_origin'):
        continue
    origin_id = key[: -len('_origin')]

    # value can be a single string or a list
    if isinstance(value, str):
        entries = [value]
    elif isinstance(value, list):
        entries = [str(v) for v in value]
    else:
        entries = []

    if not entries:
        continue

    # First entry is always the camera RTSP URL
    camera_url = entries[0]

    # Remaining entries that contain /bbox/ are bbox streams
    bbox_streams = [e for e in entries[1:] if '/bbox/' in e]

    origins[origin_id] = {
        'origin_url': camera_url,
        'bbox_streams': bbox_streams,
        'ip': extract_ip(camera_url),
    }

print(f"[YAML] Found {len(origins)} _origin streams")

# Collect _people entries  →  origin_id → people_url
people: dict[str, str] = {}
for key, value in streams.items():
    if not key.endswith('_people'):
        continue
    origin_id = key[: -len('_people')]
    if isinstance(value, list) and value:
        people[origin_id] = str(value[0])
    elif isinstance(value, str):
        people[origin_id] = value

print(f"[YAML] Found {len(people)} _people streams")

# Build IP → origin_id lookup (YAML)
ip_to_origin: dict[str, str] = {}
for origin_id, info in origins.items():
    if info['ip']:
        ip_to_origin[info['ip']] = origin_id


# ---------------------------------------------------------------------------
# Step 3: Merge
# ---------------------------------------------------------------------------

OUTPUT_FILE = 'camera_streams_map.csv'

# Collect all IPs we need to cover:
#   a) from CSV cameras matched to YAML origins
#   b) from YAML origins NOT matched to any CSV camera (c90776... case)
results: list[dict] = []

matched_csv_ips: set[str] = set()

for cam in csv_cameras:
    ip = cam['ip']
    origin_id = ip_to_origin.get(ip) if ip else None
    if origin_id:
        info = origins[origin_id]
        people_url   = people.get(origin_id, '')
        bbox_list    = info['bbox_streams']
        matched_csv_ips.add(ip)
    else:
        people_url = ''
        bbox_list  = []

    results.append({
        'cameraCode':    cam['cameraCode'],
        'name':          cam['name'],
        'ip':            ip or '',
        'origin_id':     origin_id or '',
        'origin_url':    origins[origin_id]['origin_url'] if origin_id else '',
        'bbox_streams':  ', '.join(bbox_list),
        'people_stream': people_url,
        'has_people':    'TRUE' if people_url else 'FALSE',
    })

# Add YAML-only origins (not in CSV)
for origin_id, info in origins.items():
    ip = info['ip']
    if ip and ip in ip_to_csv:
        continue  # already covered above
    if ip and ip in matched_csv_ips:
        continue
    # YAML origin that has no CSV match
    people_url = people.get(origin_id, '')
    results.append({
        'cameraCode':    '',
        'name':          f'[YAML-only] {origin_id}',
        'ip':            ip or '',
        'origin_id':     origin_id,
        'origin_url':    info['origin_url'],
        'bbox_streams':  ', '.join(info['bbox_streams']),
        'people_stream': people_url,
        'has_people':    'TRUE' if people_url else 'FALSE',
    })

# Write CSV output
FIELDNAMES = [
    'cameraCode', 'name', 'ip', 'origin_id',
    'origin_url', 'bbox_streams', 'people_stream', 'has_people',
]

with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as fh:
    writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(results)

print(f"\n[OUTPUT] Written {len(results)} rows -> {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Step 4: Summary
# ---------------------------------------------------------------------------

print("\n" + "=" * 70)
print("MATCH SUMMARY")
print("=" * 70)

matched   = [r for r in results if r['origin_id'] and r['cameraCode']]
unmatched = [r for r in results if not r['origin_id'] and r['cameraCode']]
yaml_only = [r for r in results if not r['cameraCode']]

print(f"\n[+] Matched ({len(matched)} cameras):")
for r in matched:
    print(f"   {r['cameraCode']:6s}  {r['ip']:15s}  {r['origin_id']}  has_people={r['has_people']}")

print(f"\n[-] Not found in YAML ({len(unmatched)} cameras):")
for r in unmatched:
    print(f"   {r['cameraCode']:6s}  {r['ip']:15s}  {r['name']}")

print(f"\n[!] YAML-only (no CSV match, {len(yaml_only)} cameras):")
for r in yaml_only:
    print(f"   {r['origin_id']}  ip={r['ip']}")

print("\n" + "=" * 70)
print(f"Total rows in output: {len(results)}")
print("=" * 70)
