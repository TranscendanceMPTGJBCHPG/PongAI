from pong_ql import QL_AI
import websockets
import asyncio
import json

start_event = asyncio.Event()
game_over = asyncio.Event()
ai = QL_AI(0, 0, 0, 0)


async def listen_for_messages(websocket):
    global ai

    print("in listen for messages")

    async for message in websocket:
        print(f"New message received {message}")
        event = json.loads(message)
        print(f"event: {event}")
        if event["type"] == "setup":
            ai.fromDict(event)
            ai.init_ai_modes()
            await websocket.send(json.dumps({'type': 'setup'}))
        elif event["type"] == "start":
            # Signal pour démarrer la génération des états du jeu
            start_event.set()
        elif event["type"] == "data":
            ai.getAction(event)
        await asyncio.sleep(0.001)

async def handler(websocket):
    print("handler")
    listener_task = asyncio.create_task(listen_for_messages(websocket))
    await asyncio.gather(listener_task)

async def main():
    global ai
    print("AI interface started")
    uri = "ws://localhost:7777/ws/ai/"
    # websocket = websockets.connect(uri)
    async with websockets.connect(uri) as websocket:
        print("Connected to server")
        listener_task = asyncio.create_task(listen_for_messages(websocket))
        await asyncio.gather(listener_task)
        # await handler(websocket)
        # print("Game over")
        game_over.set()
    await game_over.wait()  # Attendre le signal de fin de jeu
    # websocket.close()
    await (websocket.wait_closed())


if __name__ == "__main__":
    asyncio.run(main())