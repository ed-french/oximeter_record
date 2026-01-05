import asyncio,threading
from oximeter import Oximeter, Reading
from typing import Optional

from datetime import datetime


class ReadingStorer:
    def __init__(self):
        reading_filename=f"readings_{datetime.now().isoformat().replace(':', '-')}.txt"
        self._reading_file=open(reading_filename, "a")
        self._reading_file.write(Reading.get_csv_header() + "\n")

    def store_reading(self, reading: Reading):
        # Move cursor up and clear previous block
        for _ in range(6):
            print("\x1b[1A\x1b[2K", end="")
        print(f"Storing reading: {reading}\nQ+Enter to quit.")
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



def wait_for_quit(stop_event: asyncio.Event):
    # Run in non-async thread to poll the stdin
    while True:
        key = input().strip().lower()
        if key == "q":
            stop_event.set()
            break


# Test callback for disconnect
def on_disconnect(exc):
    print("Oximeter disconnected")
    print(f"Exception: {exc=}")



async def main():

    stop_event = asyncio.Event()

    storer = ReadingStorer()
    reconnector = Reconnector()

    ox = Oximeter(
        on_reading=storer.store_reading,
        on_disconnect=reconnector.handle_disconnect,
    )
    reconnector.set_oximeter(ox)
    
    await ox.connect()
    print("\n\n\n\n\n\n")
    # Start keyboard watcher
    threading.Thread(
        target=wait_for_quit,
        args=(stop_event,),
        daemon=True,
    ).start()

    print("Running. Press Q + Enter to quit.")

    # Wait forever until told to stop
    await stop_event.wait()

    print("Disconnecting, session over.")
    
    await ox.disconnect()
    del storer # ensure file is closed

if __name__ == "__main__":
    asyncio.run(main())
