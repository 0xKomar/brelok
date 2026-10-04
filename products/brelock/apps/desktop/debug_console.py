#!/usr/bin/env python3
"""Local BLE console for the PoC. Run --help or --demo without Bluetooth."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import queue
import random
import shutil
import sys
import time

from telemetry_monitor import DeviceMonitor, MonitorConfig
from telemetry_protocol import COMPANY_ID, SERVICE_UUID, PacketError, V2_PAYLOAD, decode_telemetry, normalize_device_id

DEMO_ID = "A1B2C3D4E5F6"
DISCOVERY_SECONDS = 5.0


def positive_number(value: str) -> float:
    result = finite_number(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("wymagana dodatnia liczba")
    return result


def finite_number(value: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("wymagana liczba") from error
    if not math.isfinite(result):
        raise argparse.ArgumentTypeError("wymagana skończona liczba")
    return result


def hardware_id(value: str) -> str:
    try:
        return normalize_device_id(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="breLock PoC — konsola telemetrii, wyłącznie obserwacja.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--demo", action="store_true", help="syntetyczne dane: spoczynek, oddalanie, utrata, powrót")
    source.add_argument("--decode-hex", metavar="HEX", help="jeden payload_hex z USB (24 B v2 / 8 B v1, bez company ID)")
    parser.add_argument("--list", action="store_true", help="lista widocznych breloków, domyślnie przez 10 s")
    parser.add_argument("--device-id", type=hardware_id, help="pełny ID; bez niego wybór jedynego breloka po 5 s")
    parser.add_argument("--duration", type=positive_number, help="czas całej sesji w sekundach; domyślnie do Ctrl+C")
    parser.add_argument("--refresh", type=positive_number, default=5.0, metavar="HZ", help="odświeżanie konsoli 0,2–20 Hz (domyślnie 5)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="kolejne wiersze zamiast odświeżanego ekranu")
    output.add_argument("--json", action="store_true", help="JSONL na stdout, również dla pipe")
    parser.add_argument("--log", type=Path, metavar="PLIK.jsonl", help="nowy lokalny plik: surowe pakiety, zdarzenia i wyniki; bez nadpisywania")
    parser.add_argument("--reference-rssi", type=finite_number, default=-59.0, metavar="DBM", help="RSSI w odległości 1 m: START -59, wymaga kalibracji")
    parser.add_argument("--path-loss", type=positive_number, default=2.2, metavar="N", help="wykładnik modelu dystansu: START 2,2")
    parser.add_argument("--rssi", type=finite_number, metavar="DBM", help="opcjonalny RSSI tylko dla --decode-hex")
    args = parser.parse_args(argv)
    if not 0.2 <= args.refresh <= 20:
        parser.error("--refresh musi być w zakresie 0,2–20 Hz")
    if args.rssi is not None and (args.decode_hex is None or not -127 <= args.rssi <= 20):
        parser.error("--rssi wymaga --decode-hex i zakresu -127..20 dBm")
    if args.decode_hex is not None and (args.list or args.device_id or args.duration):
        parser.error("--decode-hex nie łączy się z --list, --device-id ani --duration")
    if args.list and args.device_id:
        parser.error("--list pokazuje wszystkie breloki; pomiń --device-id")
    if args.demo and args.device_id and args.device_id != DEMO_ID:
        parser.error(f"ID syntetycznego breloka to {DEMO_ID}")
    if args.list and args.duration is None:
        args.duration = 10.0
    return args


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Output:
    def __init__(self, args: argparse.Namespace):
        self.json = args.json
        self.panel = (not args.json and not args.plain and sys.stdout.isatty()
                      and os.environ.get("TERM") != "dumb"
                      and (os.name != "nt" or bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON"))))
        if args.log:
            args.log.parent.mkdir(parents=True, exist_ok=True)
        self.log = args.log.open("x", encoding="utf-8") if args.log else None

    def close(self) -> None:
        if self.log:
            self.log.close()

    def record(self, kind: str, data: dict, stdout: bool = False) -> None:
        record = {"type": kind, "utc": utc_now(), **data}
        line = json.dumps(record, ensure_ascii=False, allow_nan=False)
        if self.log:
            self.log.write(line + "\n")
            self.log.flush()
        if stdout and self.json:
            print(line, flush=True)

    def message(self, message: str) -> None:
        # Human-readable errors belong on stderr, including in --json mode.
        print(message, file=sys.stderr, flush=True)

    def show(self, view: dict) -> None:
        self.record("snapshot", view, stdout=True)
        if self.json:
            return
        lines = panel_lines(view) if self.panel else []
        width, height = shutil.get_terminal_size((120, 40))
        required_rows = sum(max(1, math.ceil(len(line) / max(1, width))) for line in lines)
        if self.panel and required_rows < height:
            # Clear the old panel as well, including lines left after resize.
            sys.stdout.write("\x1b[H\x1b[2J" + "\n".join(lines) + "\n")
            sys.stdout.flush()
        else:
            print(plain_line(view), flush=True)


@dataclass(frozen=True)
class Received:
    payload: bytes
    rssi: float | None
    at: float
    address: str = ""
    name: str | None = None


class Session:
    def __init__(self, args: argparse.Namespace, output: Output, started_at: float):
        self.args, self.output, self.started_at = args, output, started_at
        self.config = MonitorConfig(reference_rssi_dbm=args.reference_rssi, path_loss_exponent=args.path_loss)
        self.source = "demo" if args.demo else "hex" if args.decode_hex is not None else "ble"
        self.selected = args.device_id or (DEMO_ID if args.demo and not args.list else None)
        self.devices: dict[str, DeviceMonitor] = {}
        self.payloads: dict[str, str] = {}
        self.scanner_status = "starting" if self.source == "ble" else self.source
        self.last_error: str | None = None
        self.invalid_packets = 0
        self.ignored_packets = 0
        self.scanner_errors = 0
        self.queue_dropped = 0
        if self.selected:
            self.devices[self.selected] = DeviceMonitor(self.selected, self.config)

    def receive(self, received: Received) -> None:
        try:
            packet = decode_telemetry(received.payload)
        except PacketError as error:
            self.invalid_packets += 1
            self.last_error = str(error)
            self.output.record("invalid_packet", {"t_s": received.at - self.started_at,
                               "payload_hex": received.payload.hex(), "error": str(error)})
            return
        if packet is None:
            self.ignored_packets += 1
            return
        monitor = self.devices.get(packet.device_id)
        if monitor is None:
            if len(self.devices) >= 64:
                self.ignored_packets += 1
                return
            monitor = self.devices[packet.device_id] = DeviceMonitor(packet.device_id, self.config)
        disposition = monitor.receive(packet, received.rssi, received.at, received.address, received.name)
        if disposition in ("new", "reboot", "legacy_callback"):
            self.payloads[packet.device_id] = received.payload.hex().upper()
        self.output.record("advertisement", {"t_s": received.at - self.started_at,
                           "source": self.source, "address": received.address, "name": received.name,
                           "rssi_dbm": received.rssi if received.rssi is not None and math.isfinite(received.rssi) else None,
                           "payload_hex": received.payload.hex().upper(),
                           "disposition": disposition, "telemetry": packet.to_dict()})

    def view(self, at: float) -> dict:
        device = self.devices[self.selected].snapshot(at) if self.selected in self.devices else None
        return {"source": self.source, "mode": "OBSERVE", "t_s": at - self.started_at,
                "scanner": self.scanner_status, "selected_id": self.selected,
                "device": device, "payload_hex": self.payloads.get(self.selected),
                "devices": [monitor.snapshot(at) for monitor in self.devices.values() if monitor.packet is not None],
                "config": asdict(self.config),
                "errors": {"invalid_packets": self.invalid_packets, "ignored_packets": self.ignored_packets,
                           "scanner_errors": self.scanner_errors, "queue_dropped": self.queue_dropped,
                           "last_error": self.last_error}}

    def choose(self, at: float) -> int:
        candidates = [identifier for identifier, monitor in self.devices.items() if monitor.packet is not None]
        if len(candidates) == 1:
            self.selected = candidates[0]
            self.output.record("selected", {"device_id": self.selected, "t_s": at - self.started_at}, stdout=True)
            return 0
        if not candidates:
            self.output.message("Nie odebrano breloka. Sprawdź firmware/Bluetooth; użyj --list lub --demo.")
            return 3
        self.output.message("Kilka breloków: " + ", ".join(candidates) + ". Uruchom ponownie z --device-id ID.")
        return 2


def value(number, unit: str = "", precision: int = 1) -> str:
    return "n/d" if number is None else f"{number:.{precision}f}{unit}"


def safe_text(text: str | None) -> str:
    # Advertising names must not inject terminal control characters.
    return "".join(character if character.isprintable() else "?" for character in text or "n/d")[:80]


def panel_lines(view: dict) -> list[str]:
    prefix = "DEMO — dane syntetyczne" if view["source"] == "demo" else "Payload USB" if view["source"] == "hex" else "BLE na żywo"
    lines = [f"breLock | {prefix} | OBSERVE | {view['t_s']:.1f} s | skaner: {view['scanner']}",
             "Dystans i prędkość radialna są estymacjami RSSI. Ctrl+C kończy sesję.", ""]
    device = view["device"]
    if device is None:
        lines.append("Wykrywanie breloków… wybór jedynego ID po 5 s." if view["source"] == "ble" and not view.get("list_mode") else "Widoczne breloki:")
        lines.extend(device_list_lines(view["devices"]))
    else:
        packet, trend, counts = device["last_packet"] or {}, device["trend"], device["counters"]
        age = (">=" if device["motion_age_saturated"] else "") + value(device["motion_age_s"], " s", 2)
        recent = "n/d" if device["recent_motion"] is None else "tak" if device["recent_motion"] else "nie"
        motion = {"moving": "RUCH", "still": "SPOCZYNEK", "unknown": "NIEZNANY"}[device["motion"]]
        speed = device["radial_speed_estimate_m_s"]
        direction = " (+ oddalanie / - zbliżanie)" if speed is not None else ""
        lines += [
            f"ID: {device['device_id']} | v{device['protocol_version'] or '?'} | {device['status']}",
            f"Nazwa: {safe_text(device['name'])} | adres/UUID BLE: {safe_text(device['address'])}",
            f"Boot: {packet.get('boot_id') if packet.get('boot_id') is not None else 'n/d'} | seq: {packet.get('sequence') if packet.get('sequence') is not None else 'n/d'} | flags: {packet.get('flags', 0):#04x}",
            f"Wiek nowego pakietu: {value(device['packet_age_s'], ' s', 2)} | callbacku: {value(device['callback_age_s'], ' s', 2)}",
            f"RSSI: {value(device['rssi_raw_dbm'], ' dBm')} | mediana + EMA: {value(device['rssi_filtered_dbm'], ' dBm')}",
            f"Dystans z RSSI: ~{value(device['distance_estimate_m'], ' m', 2)} | TX nominalny: {value(device['nominal_tx_dbm'], ' dBm', 0)}",
            f"Prędkość radialna z RSSI: ~{value(speed, ' m/s', 2)}{direction}",
            "Prędkość rzeczywista: n/d — BLE v2 nie przesyła pomiaru prędkości.",
            f"Trend: {value(trend['slope_db_s'], ' dB/s', 2)} | R²: {value(trend['r_squared'], '', 2)} | {trend['quality']}",
            f"Okno trendu: {trend['points']} punktów / {trend['span_s']:.2f} s | pokrycie: {trend['coverage']:.0%} | szum resztowy: {value(trend['residual_std_db'], ' dB', 2)}",
            f"IMU: {'OK' if device['imu_valid'] else 'nieważne/brak'} | gyro: {'OK' if device['gyro_valid'] else 'nieważny/brak'} | clipping: {device['clipped']}",
            f"Ruch: {motion} | wiek ruchu: {age} | ruch w ostatnich 5 s: {recent}",
            f"Przyspieszenie dynamiczne RMS: {value(device['acceleration_rms_mg'], ' mg', 0)} / {value(device['acceleration_rms_m_s2'], ' m/s²', 3)}",
            f"Obrót RMS: {value(device['gyro_rms_dps'], ' °/s', 1)} | bateria: {value(device['battery_mv'] / 1000 if device['battery_mv'] is not None else None, ' V', 3)} | niska: {device['battery_low']}",
            f"Nowe podsumowania: {value(device['packet_hz'], ' Hz', 2)} | callbacki: {value(device['callback_hz'], ' Hz', 2)}",
            f"Pakiety: {counts['new_packets']} nowych / {counts['duplicates']} duplikatów / {counts['out_of_order']} poza kolejnością / {counts['conflicting_duplicates']} konfliktów",
            f"Pominięte seq: {counts['skipped_summaries']} | restarty breloka: {counts['reboots']} | reset filtra: {counts['signal_resets']} | zły RSSI: {counts['invalid_rssi']}",
            f"Ostatni poprawny payload: {view['payload_hex'] or 'n/d'}",
        ]
        if device["status"] in ("STALE", "LOST"):
            lines.append("Dane przeterminowane. Bieżące metry, prędkość i odczyty czujników są n/d.")
        if device["protocol_version"] == 1:
            lines.append("LEGACY v1: dostępne tylko RSSI/ID; brak IMU, baterii i licznika świeżości.")
    config, errors = view["config"], view["errors"]
    lines += ["", f"Model START: A={config['reference_rssi_dbm']:g} dBm @1m, n={config['path_loss_exponent']:g}; wymaga kalibracji.",
              f"Błędy: payload={errors['invalid_packets']} / skaner={errors['scanner_errors']} / kolejka={errors['queue_dropped']} | breloki={len(view['devices'])}"]
    if errors["last_error"]:
        lines.append("Ostatni błąd: " + safe_text(errors["last_error"]))
    return lines


def device_list_lines(devices: list[dict]) -> list[str]:
    lines = ["ID            Wersja  RSSI       Stan     Nazwa"]
    for device in sorted(devices, key=lambda device: device["device_id"]):
        lines.append(f"{device['device_id']}  v{device['protocol_version']}      {value(device['rssi_raw_dbm'], ' dBm', 0):<10} {device['status']:<8} {safe_text(device['name'])}")
    return lines + (["Brak odebranych breloków."] if not devices else [])


def plain_line(view: dict) -> str:
    prefix = "DEMO" if view["source"] == "demo" else "HEX" if view["source"] == "hex" else "BLE"
    device = view["device"]
    if device is None:
        found = ", ".join(f"{d['device_id']}(v{d['protocol_version']}, {value(d['rssi_raw_dbm'], 'dBm', 0)}, {d['status']})" for d in view["devices"]) or "brak"
        return f"[{prefix} {view['t_s']:6.1f}s] skaner={view['scanner']} breloki={found} błędy={view['errors']['scanner_errors']}"
    packet, counts, trend = device["last_packet"] or {}, device["counters"], device["trend"]
    return (f"[{prefix} {view['t_s']:6.1f}s] {device['device_id']} v{device['protocol_version'] or '?'} {device['status']} "
            f"boot={packet.get('boot_id')} seq={packet.get('sequence')} flags={packet.get('flags', 0):#04x} "
            f"wiek={value(device['packet_age_s'], 's', 2)} RSSI={value(device['rssi_raw_dbm'], 'dBm')} "
            f"EMA={value(device['rssi_filtered_dbm'], 'dBm')} d~={value(device['distance_estimate_m'], 'm', 2)} "
            f"v_rad~={value(device['radial_speed_estimate_m_s'], 'm/s', 2)} "
            f"trend={value(trend['slope_db_s'], 'dB/s', 2)} R2={value(trend['r_squared'], '', 2)}({trend['quality']}) "
            f"ruch={device['motion']} wiek_ruchu={'>' if device['motion_age_saturated'] else ''}{value(device['motion_age_s'], 's', 2)} "
            f"acc_RMS={value(device['acceleration_rms_mg'], 'mg', 0)} gyro_RMS={value(device['gyro_rms_dps'], 'deg/s')} "
            f"bateria={value(device['battery_mv'], 'mV', 0)} low={device['battery_low']} clip={device['clipped']} "
            f"TX={value(device['nominal_tx_dbm'], 'dBm', 0)} Hz={value(device['packet_hz'], '', 2)} "
            f"nowe/dup/skip/old={counts['new_packets']}/{counts['duplicates']}/{counts['skipped_summaries']}/{counts['out_of_order']} "
            f"błędy={view['errors']['invalid_packets']}/{view['errors']['scanner_errors']}/{view['errors']['queue_dropped']}")


def scanner_options() -> dict:
    options = {"scanning_mode": "active"}
    if sys.platform == "darwin":
        version = tuple(int(part) for part in platform.mac_ver()[0].split(".")[:2])
        if (12, 0) <= version < (12, 3):
            options["service_uuids"] = [SERVICE_UUID]
    return options


async def scan_forever(session: Session, incoming: queue.Queue, stopped: asyncio.Event, scanner_factory) -> None:
    def callback(device, advertisement):
        payload = advertisement.manufacturer_data.get(COMPANY_ID)
        if payload is None:
            return
        received = Received(bytes(payload), advertisement.rssi, time.monotonic(), device.address,
                            advertisement.local_name or device.name)
        try:
            incoming.put_nowait(received)
        except queue.Full:
            session.queue_dropped += 1
            # Preserve recent observations rather than process a long backlog.
            with suppress(queue.Empty):
                incoming.get_nowait()
            with suppress(queue.Full):
                incoming.put_nowait(received)

    attempt = 0
    while not stopped.is_set():
        session.scanner_status = "starting"
        try:
            async with scanner_factory(detection_callback=callback, **scanner_options()):
                session.scanner_status = "scanning"
                attempt = 0
                await stopped.wait()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            attempt += 1
            session.scanner_errors += 1
            session.last_error = str(error) or type(error).__name__
            session.scanner_status = "unavailable/retrying"
            session.output.record("scanner_error", {"t_s": time.monotonic() - session.started_at,
                                  "error": session.last_error, "attempt": attempt}, stdout=True)
            session.output.message("Błąd skanera BLE: " + session.last_error)
            try:
                await asyncio.wait_for(stopped.wait(), timeout=min(5.0, 0.5 * 2 ** min(attempt - 1, 4)))
            except asyncio.TimeoutError:
                pass


async def demo_source(incoming: queue.Queue, stopped: asyncio.Event) -> None:
    rng = random.Random(42)
    index = 0
    started = time.monotonic()
    while not stopped.is_set():
        elapsed = time.monotonic() - started
        phase = elapsed % 32.0
        # 0..5 still; 5..14 move away; 14..22 no reception; 22..32 return.
        if not 14 <= phase < 22:
            moving = phase >= 5
            baseline = -56.0 if phase < 5 else -56 - 2.0 * (phase - 5) if phase < 14 else -74 + 1.8 * (phase - 22)
            payload = V2_PAYLOAD.pack(2, 1, bytes.fromhex(DEMO_ID), 0x1234, index & 0xFFFFFFFF,
                                     0x17 if moving else 0x16, 140 if moving else 12,
                                     240 if moving else 8, 0 if moving else 65535, 3980, 3)
            received = Received(payload, round(baseline + rng.gauss(0, 1.1)), time.monotonic(), "DEMO", "breLock demo")
            incoming.put_nowait(received)
            # Exercise duplicate handling, without inventing fresh summaries.
            if index % 3 == 0:
                incoming.put_nowait(received)
        index += 1
        await asyncio.sleep(0.2)


async def run_session(args: argparse.Namespace, output: Output, scanner_factory=None) -> int:
    if not args.demo and scanner_factory is None:
        try:
            from bleak import BleakScanner
        except ImportError:
            output.message("Brak Bleak. Zainstaluj: python -m pip install -r requirements-console.txt")
            return 2
        scanner_factory = BleakScanner
    session = Session(args, output, time.monotonic())
    output.record("session", {"source": session.source, "mode": "OBSERVE", "config": asdict(session.config),
                  "selected_id": session.selected, "duration_s": args.duration,
                  "actual_speed_available": False}, stdout=True)
    output.message("breLock: obserwacja telemetrii. Dystans/prędkość radialna z RSSI są szacowane; Ctrl+C kończy sesję.")
    incoming: queue.Queue = queue.Queue(maxsize=512)
    stopped = asyncio.Event()
    source = asyncio.create_task(demo_source(incoming, stopped) if args.demo
                                 else scan_forever(session, incoming, stopped, scanner_factory))
    discovery_started: float | None = None
    exit_code = 0
    try:
        while True:
            if source.done():
                source.result()
            for _ in range(512):
                try:
                    session.receive(incoming.get_nowait())
                except queue.Empty:
                    break
            at = time.monotonic()
            if session.scanner_status == "scanning" and discovery_started is None:
                discovery_started = at
            if not args.list and session.selected is None and discovery_started is not None and at - discovery_started >= DISCOVERY_SECONDS:
                exit_code = session.choose(at)
                if exit_code:
                    output.show(session.view(at))
                    break
            view = session.view(at)
            view["list_mode"] = args.list
            output.show(view)
            if args.duration is not None and at - session.started_at >= args.duration:
                if session.scanner_errors and session.scanner_status != "scanning":
                    exit_code = 2
                elif ((session.selected is not None and session.devices[session.selected].packet is None)
                      or (session.selected is None and not any(monitor.packet is not None for monitor in session.devices.values()))):
                    exit_code = 3
                break
            delay = 1.0 / args.refresh
            if args.duration is not None:
                delay = min(delay, max(0.0, args.duration - (at - session.started_at)))
            await asyncio.sleep(delay)
    finally:
        stopped.set()
        source.cancel()
        with suppress(asyncio.CancelledError):
            await source
        output.record("end", {"source": session.source, "t_s": time.monotonic() - session.started_at,
                              "selected_id": session.selected, "exit_code": exit_code}, stdout=True)
    return exit_code


def decode_once(args: argparse.Namespace, output: Output) -> int:
    try:
        payload = bytes.fromhex(args.decode_hex)
        packet = decode_telemetry(payload)
        if packet is None:
            raise PacketError("To nie jest obsługiwany payload breLock v1/v2")
    except ValueError as error:
        output.message("Nieprawidłowy payload: " + str(error))
        return 2
    session = Session(args, output, 0.0)
    session.selected = packet.device_id
    session.receive(Received(payload, args.rssi, 0.0, "USB HEX", "breLock"))
    view = session.view(0.0)
    if args.json:
        output.show(view)
    else:
        print("\n".join(panel_lines(view)))
        output.record("snapshot", view)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = arguments(argv)
    try:
        output = Output(args)
    except OSError as error:
        print(f"Nie można otworzyć nowego logu: {error}", file=sys.stderr)
        return 2
    try:
        return decode_once(args, output) if args.decode_hex is not None else asyncio.run(run_session(args, output))
    except KeyboardInterrupt:
        output.message("Sesja zakończona.")
        return 0
    except BrokenPipeError:
        # A consumer such as `head` has intentionally stopped reading.
        return 0
    except (OSError, ValueError) as error:
        output.message("Błąd konsoli: " + str(error))
        return 2
    finally:
        output.close()


if __name__ == "__main__":
    raise SystemExit(main())
