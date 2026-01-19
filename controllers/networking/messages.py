import asyncio

ws_queu_sender = asyncio.Queue()
ws_queu_receiver = asyncio.Queue()


async def send_msg_sender(msg):
    await ws_queu_sender.put(msg)


async def get_msg_sender():
    return await ws_queu_sender.get()


async def send_msg_receiver(msg):
    await ws_queu_receiver.put(msg)


async def get_msg_receiver():
    return await ws_queu_receiver.get()
