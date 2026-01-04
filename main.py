import asyncio
from oximeter import Oximeter, Reading
from typing import Optional

from datetime import datetime


class ReadingStorer:
    def __init__(self):
        reading_filename=f"readings_{datetime.now().isoformat().replace(':', '-')}.txt"
        self._reading_file=open(reading_filename, "a")
        self._reading_file.write(Reading.get_csv_header() + "\n")

    def store_reading(self, reading: Reading):
        print(f"Storing reading: {reading}")
        self._reading_file.write(reading.get_csv_line() + "\n")
        self._reading_file.flush()

    def __del__(self):
        self._reading_file.close()

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




# Test callback for disconnect
def on_disconnect(exc):
    print("Oximeter disconnected")
    print(f"Exception: {exc=}")



async def main():
    storer = ReadingStorer()
    reconnector = Reconnector()

    ox = Oximeter(
        on_reading=storer.store_reading,
        on_disconnect=reconnector.handle_disconnect,
    )
    reconnector.set_oximeter(ox)
    
    await ox.connect()

    await asyncio.sleep(200)
    print("Disconnecting, session over.")
    del storer
    await ox.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
