import time, socket, asyncio

async def main():
    loop = asyncio.get_event_loop()
    srv = await loop.create_server(lambda: asyncio.Protocol(), '0.0.0.0', 8000)
    out = open("logs/test_alive.log", "w", buffering=1)
    for i in range(60):
        out.write(f"{i}\n")
        out.flush()
        await asyncio.sleep(1)
    out.close()
    srv.close()

asyncio.run(main())
