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



def wait_for_quit(stop_event: asyncio.Event):
    # Run in non-async thread to poll the stdin
    while True:
        key = input().strip().lower()
        if key == "q":
            stop_event.set()
            break





async def main():

    stop_event = asyncio.Event()

    storer = ReadingStorer()

    ox = Oximeter(
        on_reading=storer.store_reading,
        auto_reconnect=True
    )
    
    
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
