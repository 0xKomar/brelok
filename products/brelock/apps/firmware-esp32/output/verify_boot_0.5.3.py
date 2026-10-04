"""Verify the uploaded fob and three hardware resets; keep the local trace."""
import json
import time
from pathlib import Path
import serial

root = Path(__file__).parent
link = serial.Serial(port=None, baudrate=115200, timeout=0.15)
link.dtr = False
link.rts = False
link.port = '/dev/cu.usbmodem5B910447981'
records = []
boot_lines = []


def capture(phase, seconds, expected_boot=None):
    observations = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = link.readline().decode('utf-8', 'replace').strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            boot_lines.append(f'{phase}: {line}')
            if 'panic' in line or 'Guru' in line:
                raise RuntimeError(f'{phase}: {line}')
            continue
        if value.get('type') == 'status':
            observations.append(value)
            records.append({'verification_phase': phase, **value})
    if len(observations) < 4:
        raise RuntimeError(f'{phase}: only {len(observations)} status records')
    boot_ids = {record['boot_id'] for record in observations}
    if len(boot_ids) != 1:
        raise RuntimeError(f'{phase}: unexpected reboot {boot_ids}')
    if expected_boot is not None and boot_ids != {expected_boot}:
        raise RuntimeError(f'{phase}: boot changed from {expected_boot} to {boot_ids}')
    last = observations[-1]
    if last['firmware'] != '0.5.3-poc' or last['device_id'] != '142D6F020F3C':
        raise RuntimeError(f'{phase}: unexpected firmware/device')
    if not (last['ble_ok'] and last['touch_ready'] and last['motion_valid']):
        raise RuntimeError(f'{phase}: hardware not ready')
    if any(record[key] != 0 for record in observations
           for key in ['ble_errors', 'imu_errors', 'touch_errors']):
        raise RuntimeError(f'{phase}: hardware error')
    print(json.dumps({'phase': phase, 'records': len(observations), 'boot_id': last['boot_id'],
                      'uptime_ms': last['uptime_ms'], 'imu_hz': last['imu_hz'],
                      'gatt_connected': last['gatt_connected'], 'host_fresh': last['host_fresh'],
                      'host_calibration': last['host_calibration']}), flush=True)
    return last['boot_id']


try:
    with link:
        link.write(b's')
        capture('after_upload', 8)
        for cycle in range(1, 4):
            link.reset_input_buffer()
            link.dtr = False
            link.rts = True
            time.sleep(0.15)
            link.rts = False
            last_boot = capture(f'reset_{cycle}', 8)
        capture('continuous', 10, last_boot)
        link.write(b'w')
        print('PASS: firmware, 3 hardware resets, continued operation and sensor status', flush=True)
finally:
    (root / 'startup-verify-0.5.3.jsonl').write_text(
        ''.join(json.dumps(record) + '\n' for record in records))
    (root / 'startup-verify-0.5.3-boot.log').write_text('\n'.join(boot_lines) + '\n')
