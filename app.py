import time

from pong_ql import QL_AI
import websockets
import asyncio
import json
import urllib.request
import urllib.error
import logging
# import aiohttp
import ssl

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

start_event = asyncio.Event()
game_over = asyncio.Event()

ai_instances = {}
ai_instances['easy'] = QL_AI(1500, 1000, 6, 166, 1, "right")
ai_instances['medium'] = QL_AI(1500, 1000, 6, 166, 2, "right")
ai_instances['hard'] = QL_AI(1500, 1000, 6, 166, 3, "right")
ai_instances['easy_p1'] = QL_AI(1500, 1000, 6, 166, 1, "left")
ai_instances['medium_p1'] = QL_AI(1500, 1000, 6, 166, 2, "left")
ai_instances['hard_p1'] = QL_AI(1500, 1000, 6, 166, 3, "left")

game_instances = {}

async def listen_for_messages(websocket, game_uid):
    try:
        while True:
            try:
                message = await websocket.recv()
                event = json.loads(message)
                if event["type"] == "setup":
                    await websocket.send(json.dumps({'type': 'setup', 'sender': 'AI'}))
                elif event["type"] == "None":
                    await process_and_send_action(websocket, event, game_uid)
                await asyncio.sleep(0.001)
            except asyncio.TimeoutError:
                continue
    except websockets.exceptions.ConnectionClosedError:
        print(f"Connection closed for game {game_uid}")
        await cleanup_ai_instance(game_uid)
        return


async def process_and_send_action(websocket, event, uid):
    action = await game_instances[uid]['ai'].getAction(event)
    if action == "Error":
        del game_instances[uid]
        #stop the
        return

    await websocket.send(json.dumps({"type": "move", "direction": str(action), 'sender': 'AI'}))
    # print(f"Sent action: {action}")


async def handler(websocket):
    print("handler")
    listener_task = asyncio.create_task(listen_for_messages(websocket))
    await asyncio.gather(listener_task)


# Réception d'UID de jeu via le serveur AI


async def join_game(uid):
    uri = f"wss://nginx:7777/ws/pong/{uid}/"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print(f"IA connectée à la partie {uid}")
            await websocket.send(json.dumps({"type": "greetings", "sender": "AI"}))
            await listen_for_messages(websocket, uid)
    except Exception as e:
        logging.error(f"Error in join_game for {uid}: {e}")
        await cleanup_ai_instance(uid)

async def continuous_listen_for_uid():
    """Fonction qui cherche continuellement des nouvelles parties"""
    while True:
        try:
            response = requests.get("https://nginx:7777/game/join/?mode=AI", verify=False)
            if response.status_code == 200:
                data = response.json()
                logging.info(f"Checking for new game: {data}")
                if data.get('uid') != 'error':
                    uid = data['uid']
                    if uid not in game_instances:  # Vérifier qu'on ne gère pas déjà cette partie
                        add_game_instance(uid)
                        asyncio.create_task(join_game(uid))  # Créer une nouvelle tâche sans l'attendre
                        logging.info(f"Joining new game: {uid}")
        except Exception as e:
            logging.error(f"Error in continuous_listen_for_uid: {e}")

        await asyncio.sleep(3)  # Attendre avant la prochaine vérification


def add_game_instance(uid):
    game_instances[uid] = {}

    if uid[0] == '1':
        if uid[-1] == '1':
            game_instances[uid]['ai'] = ai_instances['easy_p1']
        else:
            game_instances[uid]['ai'] = ai_instances['easy']
    elif uid[0] == '2':
        if uid[-1] == '1':
            game_instances[uid]['ai'] = ai_instances['medium_p1']
        else:
            game_instances[uid]['ai'] = ai_instances['medium']
    elif uid[0] == '3':
        if uid[-1] == '1':
            game_instances[uid]['ai'] = ai_instances['hard_p1']
        else:
            game_instances[uid]['ai'] = ai_instances['hard']

async def cleanup_ai_instance(uid):
    """Nettoie l'instance d'IA pour une partie terminée"""
    if uid in game_instances:
        del game_instances[uid]
        logging.info(f"Cleaned up AI instance for game {uid}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Exécuter la boucle principale de recherche de parties
    asyncio.run(continuous_listen_for_uid())