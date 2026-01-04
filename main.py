import asyncio
from oximeter import Oximeter, Reading

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


def on_reading(r: Reading):
    print(r)

# Test callback for disconnect
def on_disconnect(exc):
    print("Oximeter disconnected")
    print(f"Exception: {exc=}")

async def main():
    r = ReadingStorer()
    ox = Oximeter(
        on_reading=r.store_reading,
        on_disconnect=on_disconnect,
    )
    
    await ox.connect()
    await asyncio.sleep(30)
    print("Disconnecting, session over.")
    del r
    await ox.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
