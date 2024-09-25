import time

from pong_ql import QL_AI
import websockets
import asyncio
import json
import urllib.request
import urllib.error

start_event = asyncio.Event()
game_over = asyncio.Event()

ai_instances = {}
ai_instances['easy'] = QL_AI(1500, 1000, 6, 166, 1)
ai_instances['medium'] = QL_AI(1500, 1000, 6, 166, 2)
ai_instances['hard'] = QL_AI(1500, 1000, 6, 166, 3)

game_instances = {}

async def listen_for_messages(websocket, game_uid):
    global ai_instances

    timestamp = 0
    if time.time() - timestamp > 0.1:
        timestamp = time.time()
    print("in listen for messages")
    try:
        if time.time() - timestamp < 0.1:
            timestamp = time.time()
        while True:
            try:
                message = await websocket.recv()
                if time.time() - timestamp < 0.1:
                    timestamp = time.time()
                event = json.loads(message)
                if event["type"] == "setup":
                    await websocket.send(json.dumps({'type': 'setup', 'sender': 'AI'}))
                elif event["type"] == "None":
                    await process_and_send_action(websocket, event, game_uid)
                await asyncio.sleep(0.001)
            except asyncio.TimeoutError:
                print("No message received in the last 10 seconds")
                continue
    except websockets.exceptions.ConnectionClosedError:
        print("Connection closed")
        game_over.set()
        return


async def process_and_send_action(websocket, event, uid):
    action = await game_instances[uid]['ai'].getAction(event)
    await websocket.send(json.dumps({"type": "move", "direction": str(action), 'sender': 'AI'}))
    print(f"Sent action: {action}")


async def handler(websocket):
    print("handler")
    listener_task = asyncio.create_task(listen_for_messages(websocket))
    await asyncio.gather(listener_task)


async def get_uri():
    try:
        url = 'http://nginx:7777/game/new/'
        data = {
            'type': 'PVE',
            'sender': 'AI'
        }
        headers = {
            'Content-Type': 'application/json'
        }

        # Convertir le corps de la requête en JSON
        data = json.dumps(data).encode('utf-8')

        # Créer l'objet Request
        req = urllib.request.Request(url, data=data, headers=headers, method='GET')

        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            print(f"UID: {data['uid']}")
            return data['uid']

    except urllib.error.HTTPError as e:
        print(e.reason)


# Réception d'UID de jeu via le serveur AI
async def join_game(uid):
    uri = f"ws://server:8000/ws/pong/{uid}/"
    async with websockets.connect(uri) as websocket:
        # print(f"IA connectée à la partie {uid}")
        await websocket.send(json.dumps({"type": "greetings", "sender": "AI"}))
        # print("Message de salutation envoyé")
        await listen_for_messages(websocket, uid)


# Continuously fetching the route 'http://nginx:7777/game/new/?mode=AI'
# On response, get the uid and join the game
async def listen_for_uid():
    url = "http://nginx:7777/game/new/?mode=AI"
    while True:
        #fetch the url to get the uid
        try:
            response = urllib.request.urlopen(url)
            data = json.loads(response.read())
            print(data)
            #check if the data key is not error
            if 'error' in data:
                # print(data['error'])
                pass
            else:
                uid = data['uid']
                add_game_instance(uid)
                # print(f"UID: {uid}")
                asyncio.create_task(join_game(uid))
            await asyncio.sleep(3)
        except urllib.error.HTTPError as e:
            print(e.reason)


def add_game_instance(uid):
    game_instances[uid] = {}

    if uid[0] == '1':
        game_instances[uid]['ai'] = ai_instances['easy']
    elif uid[0] == '2':
        game_instances[uid]['ai'] = ai_instances['medium']
    elif uid[0] == '3':
        game_instances[uid]['ai'] = ai_instances['hard']

async def main():
    await listen_for_uid()


if __name__ == "__main__":
    asyncio.run(main())