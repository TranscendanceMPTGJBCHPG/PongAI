import time

from pong_ql import QL_AI
import websockets
import asyncio
import json

start_event = asyncio.Event()
game_over = asyncio.Event()
ai = QL_AI(0, 0, 0, 0)


async def listen_for_messages(websocket):
    global ai
    timestamp = 0
    if time.time() - timestamp > 0.1:
        await websocket.send(json.dumps({'type': 'ping', 'sender': 'AI'}))
        timestamp = time.time()
        print("ping sent")
    print("in listen for messages")
    try:
        if time.time() - timestamp < 0.1:
            await websocket.send(json.dumps({'type': 'ping', 'sender': 'AI'}))
            timestamp = time.time()
            print("ping sent")
        async for message in websocket:
            if time.time() - timestamp < 0.1:
                await websocket.send(json.dumps({'type': 'ping', 'sender': 'AI'}))
                timestamp = time.time()
                print("ping sent")
            print(f"New message received {message}")
            event = json.loads(message)
            # print(f"event: {event}")
            if event["type"] == "setup":
                ai.fromDict(event)
                ai.init_ai_modes()
                await websocket.send(json.dumps({'type': 'setup', 'sender': 'AI'}))
            elif event["type"] == "data":
                await process_and_send_action(websocket, event)
                # websocket.send(ai.getAction(repr(event["state"])))
            await asyncio.sleep(0.001)
    except websockets.exceptions.ConnectionClosedError:
        print("Connection closed")
        game_over.set()
        return

async def process_and_send_action(websocket, event):
    global ai
    action = ai.getAction(repr(event["state"]))
    await websocket.send(json.dumps({"type": "move", "direction": str(action), 'sender': 'AI'}))
    print(f"Sent action: {action}")
async def handler(websocket):
    print("handler")
    listener_task = asyncio.create_task(listen_for_messages(websocket))
    await asyncio.gather(listener_task)

async def main():
    global ai
    print("AI interface started")
    uri = "ws://server:8001/ws/pong/"
    # websocket = websockets.connect(uri)
    async with websockets.connect(uri) as websocket:
        print("Connected to server")
        await websocket.send(json.dumps({'type': 'greetings', 'sender': 'AI'}))
        print(f"Sent greetings to {websocket}")
        await asyncio.sleep(0.1)
        await listen_for_messages(websocket)
    await game_over.wait()  # Attendre le signal de fin de jeu
    await (websocket.wait_closed())


if __name__ == "__main__":
    asyncio.run(main())