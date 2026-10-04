import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from debug_console import Output, Received, Session, arguments, main, panel_lines, run_session
from test_telemetry_protocol import GOLDEN, GOLDEN_HEX


class MemoryOutput:
    def __init__(self):
        self.records, self.messages, self.views = [], [], []

    def record(self, kind, data, stdout=False):
        self.records.append((kind, data))

    def message(self, message):
        self.messages.append(message)

    def show(self, view):
        self.views.append(view)


class ConsoleTests(unittest.TestCase):
    def session(self, *flags):
        return Session(arguments(list(flags)), MemoryOutput(), 0.0)

    def test_full_id_matches_without_local_name_or_bluetooth_mac(self):
        session = self.session("--device-id", "12:34:56:78:9A:BC")
        session.receive(Received(GOLDEN, -65, 0, "CoreBluetooth-UUID", None))
        device = session.view(0)["device"]
        self.assertEqual(device["status"], "LIVE")
        self.assertEqual(device["device_id"], "123456789ABC")
        self.assertEqual(device["address"], "CoreBluetooth-UUID")
        self.assertIsNone(device["name"])

    def test_auto_selection_requires_exactly_one_id(self):
        none = self.session()
        self.assertEqual(none.choose(5), 3)
        single = self.session()
        single.receive(Received(GOLDEN, -65, 0))
        self.assertEqual(single.choose(5), 0)
        self.assertEqual(single.selected, "123456789ABC")
        second = bytearray(GOLDEN)
        second[2:8] = bytes.fromhex("AABBCCDDEEFF")
        multiple = self.session()
        multiple.receive(Received(GOLDEN, -65, 0))
        multiple.receive(Received(second, -50, 1))
        self.assertEqual(multiple.choose(5), 2)
        self.assertIsNone(multiple.selected)

    def test_malformed_packet_does_not_refresh_previous_telemetry(self):
        session = self.session("--device-id", "123456789ABC")
        session.receive(Received(GOLDEN, -65, 0))
        session.receive(Received(GOLDEN[:-1], -50, 2))
        self.assertEqual(session.invalid_packets, 1)
        self.assertEqual(session.view(2)["device"]["status"], "STALE")
        self.assertEqual(session.payloads[session.selected], GOLDEN_HEX)

    def test_jsonl_contains_raw_packets_settings_and_snapshots_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "logs" / "trace.jsonl"
            args = arguments(["--device-id", "123456789ABC", "--log", str(filename)])
            output = Output(args)
            try:
                session = Session(args, output, 0)
                session.receive(Received(GOLDEN, math.nan, 0))
                output.record("snapshot", session.view(0))
            finally:
                output.close()
            rows = [json.loads(line) for line in filename.read_text().splitlines()]
            self.assertEqual(rows[0]["type"], "advertisement")
            self.assertEqual(rows[0]["payload_hex"], GOLDEN_HEX)
            self.assertIsNone(rows[0]["rssi_dbm"])
            self.assertEqual(rows[1]["config"]["reference_rssi_dbm"], -59)
            self.assertEqual(rows[1]["device"]["counters"]["invalid_rssi"], 1)
            with self.assertRaises(FileExistsError):
                Output(args)

    def test_offline_hex_mode_reports_units_without_bluetooth_dependency(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = main(["--decode-hex", GOLDEN_HEX, "--json"])
        self.assertEqual(result, 0)
        view = json.loads(stdout.getvalue())
        self.assertEqual(view["source"], "hex")
        self.assertEqual(view["device"]["gyro_rms_dps"], 45.6)
        self.assertIsNone(view["device"]["actual_speed_m_s"])

    def test_invalid_hex_is_a_useful_error_without_traceback(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(main(["--decode-hex", "not-hex"]), 2)
        self.assertIn("Nieprawidłowy payload", stderr.getvalue())

    def test_invalid_arguments_are_rejected(self):
        for flags in (["--path-loss", "0"], ["--duration", "nan"], ["--refresh", "21"],
                      ["--device-id", "breLock"], ["--reference-rssi", "inf"], ["--rssi", "-60"],
                      ["--list", "--device-id", "123456789ABC"], ["--demo", "--decode-hex", GOLDEN_HEX]):
            with self.subTest(flags=flags), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                arguments(flags)

    def test_terminal_names_cannot_inject_control_characters(self):
        session = self.session("--device-id", "123456789ABC")
        session.receive(Received(GOLDEN, -65, 0, name="name\x1b[2J\nattack"))
        text = "\n".join(panel_lines(session.view(0)))
        self.assertNotIn("\x1b", text)
        self.assertIn("name?[2J?attack", text)


class ScannerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def factory(self, payload=GOLDEN, fail_first=False, fail_always=False):
        instances = []

        class FakeScanner:
            def __init__(self, **options):
                self.callback = options["detection_callback"]
                self.options, self.stopped = options, False
                instances.append(self)

            async def __aenter__(self):
                if fail_always or fail_first and len(instances) == 1:
                    raise RuntimeError("Bluetooth disabled")
                self.callback(SimpleNamespace(address="OS-UUID", name=None),
                              SimpleNamespace(manufacturer_data={0xFFFF: payload}, rssi=-64, local_name=None))
                return self

            async def __aexit__(self, *args):
                self.stopped = True

        return FakeScanner, instances

    async def test_callback_uses_advertisement_rssi_and_stops_scanner_at_deadline(self):
        factory, instances = self.factory()
        args = arguments(["--device-id", "123456789ABC", "--duration", "0.12", "--refresh", "20"])
        output = MemoryOutput()
        self.assertEqual(await run_session(args, output, factory), 0)
        device = output.views[-1]["device"]
        self.assertEqual(device["rssi_raw_dbm"], -64)
        self.assertEqual(device["gyro_rms_dps"], 45.6)
        self.assertEqual(instances[0].options["scanning_mode"], "active")
        self.assertTrue(instances[0].stopped)

    async def test_start_failure_keeps_diagnostics_running_and_deadline_bounded(self):
        factory, _ = self.factory(fail_always=True)
        args = arguments(["--list", "--duration", "0.12", "--refresh", "20"])
        output = MemoryOutput()
        self.assertEqual(await run_session(args, output, factory), 2)
        self.assertGreaterEqual(len(output.views), 2)
        self.assertEqual(output.views[-1]["errors"]["last_error"], "Bluetooth disabled")

    async def test_scanner_retries_after_start_failure(self):
        factory, instances = self.factory(fail_first=True)
        args = arguments(["--device-id", "123456789ABC", "--duration", "0.7", "--refresh", "20"])
        output = MemoryOutput()
        self.assertEqual(await run_session(args, output, factory), 0)
        self.assertEqual(len(instances), 2)
        self.assertTrue(instances[-1].stopped)
        self.assertEqual(output.views[-1]["device"]["status"], "LIVE")

    async def test_other_keyfob_cannot_satisfy_requested_id(self):
        factory, _ = self.factory()
        args = arguments(["--device-id", "AABBCCDDEEFF", "--duration", "0.12", "--refresh", "20"])
        output = MemoryOutput()
        self.assertEqual(await run_session(args, output, factory), 3)
        self.assertEqual(output.views[-1]["device"]["status"], "WAITING")

    async def test_cancellation_stops_scanner(self):
        factory, instances = self.factory()
        args = arguments(["--device-id", "123456789ABC", "--refresh", "20"])
        task = asyncio.create_task(run_session(args, MemoryOutput(), factory))
        await asyncio.sleep(0.06)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(instances[0].stopped)


if __name__ == "__main__":
    unittest.main()
