import logging
import threading

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)


import asyncio
from bleak import BleakClient
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional


DEFAULT_BT_ADDRESS = "C4:39:30:38:17:25"

"""
[Service] 00001800-0000-1000-8000-00805f9b34fb
  [Char] 00002a00-0000-1000-8000-00805f9b34fb (write,read)
  [Char] 00002a01-0000-1000-8000-00805f9b34fb (write,read)
  [Char] 00002a04-0000-1000-8000-00805f9b34fb (read)
  [Char] 00002ac9-0000-1000-8000-00805f9b34fb (read)
[Service] 00001801-0000-1000-8000-00805f9b34fb
  [Char] 00002a05-0000-1000-8000-00805f9b34fb (read,indicate)
[Service] 0000ffe0-0000-1000-8000-00805f9b34fb
  [Char] 0000ffe1-0000-1000-8000-00805f9b34fb (write-without-response,write,read,notify)
  [Char] 0000ffe2-0000-1000-8000-00805f9b34fb (write-without-response,write,read,notify)"""

DEFAULT_OXIMETER_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb" 





@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    spo2: int              # %
    pulse_bpm: int         # bpm
    perfusion_index: int | None
    finger_detected: bool
    raw: bytes             # original packet

    def __str__(self) -> str:
        return (
            f"Reading(timestamp={self.timestamp},\n"
            f"\tspo2={self.spo2},\n"
            f"\tpulse_bpm={self.pulse_bpm},\n"
            f"\tperfusion_index={self.perfusion_index},\n"
            f"\tfinger_detected={self.finger_detected})"
        )


    def get_csv_header() -> str:
        return "timestamp,spo2,pulse_bpm,perfusion_index,finger_detected"
    
    def get_csv_line(self) -> str:
        return (
            f"{self.timestamp.isoformat()},"
            f"{self.spo2},"
            f"{self.pulse_bpm},"
            f"{self.perfusion_index if self.perfusion_index is not None else ''},"
            f"{int(self.finger_detected)}"
        )



class Oximeter:
    def __init__(
        self,
        address: str|None = None,
        service_uuid:str|None = None,
        on_reading: Callable[[Reading], None]=None,
        on_disconnect: Optional[Callable[[Exception | None], None]] = None,
        auto_reconnect: bool = False,
    ):
        if address is None:
            address = DEFAULT_BT_ADDRESS
        self._address = address
        if service_uuid is None:
            service_uuid = DEFAULT_OXIMETER_CHAR_UUID
        self._service_uuid = service_uuid
        self._on_reading = on_reading
        self._on_disconnect = on_disconnect

        self._client: BleakClient | None = None
        self._connected = False
        if auto_reconnect:
            self._reconnector = Reconnector(self)
            self._on_disconnect = self._reconnector.handle_disconnect

    def _decode_packet(self, data: bytearray) -> Optional[Reading]:
        # Summary packets start with 0xFF
        if len(data) < 6 or data[0] != 0xFF:
            return None

        try:
            return Reading(
                timestamp=datetime.utcnow(),
                spo2=int(data[4]),
                pulse_bpm=int(data[5]),
                perfusion_index=int(data[1]),
                finger_detected=bool(data[2]),
                raw=bytes(data),
            )
        except (IndexError, ValueError):
            return None

    def _handle_notify(self, sender: int, data: bytearray):
        reading = self._decode_packet(data)
        if reading and self._on_reading:
            self._on_reading(reading)

    async def connect(self):
        if self._connected:
            return

        self._client = BleakClient(
            self._address,
            disconnected_callback=self._handle_disconnect,
        )

        await self._client.connect()
        await self._client.start_notify(
            self._service_uuid,
            self._handle_notify,
        )

        self._connected = True

    def _handle_disconnect(self, client: BleakClient):
        self._connected = False
        if self._on_disconnect:
            self._on_disconnect(None)

    async def disconnect(self):
        if not self._client:
            return

        try:
            await self._client.stop_notify(self._service_uuid)
        finally:
            await self._client.disconnect()
            self._connected = False


class Reconnector:
    def __init__(self, oximeter: Oximeter|None = None):
        self._oximeter = oximeter
        self._reconnect_task: Optional[asyncio.Task] = None

    def set_oximeter(self, oximeter: Oximeter):
        self._oximeter = oximeter

    def handle_disconnect(self, exc: Exception | None):
        if not self._oximeter:
            return

        # Prevent multiple concurrent reconnect loops
        if self._reconnect_task and not self._reconnect_task.done():
            return

        loop = asyncio.get_running_loop()
        self._reconnect_task = loop.create_task(self._reconnect_loop())


    async def _reconnect_loop(self):
        print("Oximeter disconnected, attempting to reconnect...")
        while True:
            try:
                await self._oximeter.connect()
                print("Reconnected to oximeter.")
                return
            except Exception as e:
                print(f"Reconnection failed: {e}, retrying in 5 seconds...")
                await asyncio.sleep(5)


class ReadingStorer:
    def __init__(self,
                 path:str="",
                 show_readings_in_console:bool=False):
        reading_filename=f"{path}readings_{datetime.now().isoformat().replace(':', '-')}.txt"
        self._reading_file=open(reading_filename, "a")
        self._reading_file.write(Reading.get_csv_header() + "\n")
        self._show_readings_in_console = show_readings_in_console

    def store_reading(self, reading: Reading):
        if self._show_readings_in_console:
            # Move cursor up and clear previous block
            for _ in range(6):
                print("\x1b[1A\x1b[2K", end="")
            print(f"Storing reading: {reading}\nQ+Enter to quit.")
        self._reading_file.write(reading.get_csv_line() + "\n")
        self._reading_file.flush()

    def __del__(self):
        self._reading_file.close()


class QuitWatcher(threading.Thread):
    def __init__(self):
        self.quit_requested=asyncio.Event()
        super().__init__(name="quit_console_watcher", daemon=True)


    def run(self):
        # Run in non-async thread to poll the stdin
        while True:
            key = input().strip().lower()
            if key == "q":
                self.quit_requested.set()
                break

if __name__ == "__main__":
    
    # Test callback for each reading
    def on_reading(r: Reading):
        print(r)

    # Test callback for disconnect
    def on_disconnect(exc):
        print("Oximeter disconnected")
        print(f"Exception: {exc=}")
    async def main():
        ox = Oximeter(
            on_reading=on_reading,
            on_disconnect=on_disconnect,
        )

        await ox.connect()
        await asyncio.sleep(120)
        print("Disconnecting, session over.")
        await ox.disconnect()

    asyncio.run(main())

