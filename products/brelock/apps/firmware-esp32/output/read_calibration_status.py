"""Read status without toggling reset lines; only the existing 's' command is sent."""
import json
import time
from pathlib import Path
import serial

port = serial.Serial(port=None, baudrate=115200, timeout=0.2)
port.dtr = False
port.rts = False
port.port = '/dev/cu.usbmodem5B910447981'
records = []
with port:
    deadline = time.monotonic() + 16
    port.write(b's')
    while time.monotonic() < deadline:
        line = port.readline().decode('utf-8', 'replace').strip()
        if line.startswith('{'):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get('type') == 'status':
                records.append(record)
Path(__file__).with_name('calibration-live-0.5.1.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
if records:
    print(json.dumps({key: records[-1].get(key) for key in ['firmware', 'device_id', 'ble_ok', 'ble_errors', 'imu_errors', 'touch_errors', 'gatt_connected', 'host_fresh', 'host_calibration', 'host_protection', 'host_rssi_dbm']}))
    print(f'{len(records)} USB records captured')
else:
    raise SystemExit('No status records received')
