import asyncio
from oximeter import Oximeter, ReadingStorer, QuitWatcher









async def main():

    storer = ReadingStorer(show_readings_in_console=True)



    ox = Oximeter(
        on_reading=storer.store_reading,
        auto_reconnect=True
    )
    
    
    await ox.connect()
    print("\n\n\n\n\n\n")

    # Start keyboard watcher to monitor for the quit-  Q+enter in the console
    quit_watcher = QuitWatcher()
    quit_watcher.start()



    # Wait forever until told to stop
    await quit_watcher.quit_requested.wait()

    print("Disconnecting, session over.")
    
    await ox.disconnect()
    del storer # ensure file is closed

if __name__ == "__main__":
    asyncio.run(main())
