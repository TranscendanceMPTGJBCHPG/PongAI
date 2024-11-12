import time
import websockets
import asyncio
import json
import logging
import ssl
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import threading
from pong_ql import QL_AI
import random

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class GlobalAI:
    def __init__(self, width, height, paddle_height, paddle_width, difficulty, position):
        self.ai = QL_AI(width, height, paddle_height, paddle_width, difficulty, position)
        self.lock = threading.Lock()

    async def get_action(self, state, raw_pos, next_collision, pause):
        with self.lock:
            return await self.ai.getAction(state, raw_pos, next_collision, pause)


class GameAgent:

    # training = True
    training = False

    update_timestamp = 0
    limit_timestamp = 0
    game_state = None
    raw_position = None
    side = None
    next_collision = None
    pause = False
    goal = False
    difficulty = None
    min_position = None
    max_position = None


    def __init__(self, global_ai):
        self.global_ai = global_ai
        self.side = global_ai.ai.side
        self.difficulty = global_ai.ai.difficulty

        self.min_position = 83
        self.max_position = 1000 - self.min_position

#TODO: put  the timestamp to 0 on reset after a goal
#TODO: update paddle position from AI result, not game data
    async def get_action(self, state):
        if time.time() - self.limit_timestamp < 1/60:
            return 'wait'
        # logging.info(f"Received state: {state}")
        if state['type'] == 'gameover':
            return 'Error'
        self.pause = state['game']['pause']
        if self.raw_position is None:
            if self.side == "right":
                self.raw_position = state["paddle2"]["y"] * 1000
            else:
                self.raw_position = state["paddle1"]["y"] * 1000
            logging.info(f"Initial position: {self.raw_position}")
        # else:
        #     if self.side == "right":
        #         if self.raw_position != state["paddle2"]["y"] * 1000:
        #             logging.info(f"In loop : Error in Raw position: {self.raw_position}, state position: {state['paddle2']['y'] * 1000}\n\n")
        #             # exit(0)
        #     else:
        #         if self.raw_position != state["paddle1"]["y"] * 1000:
        #             logging.info(f"In loop : Error in Raw position: {self.raw_position}, state position: {state['paddle1']['y'] * 1000}\n\n")
        #             # exit(0)
        if state["resumeOnGoal"] is True:
            self.update_timestamp = 0
        if time.time() - self.update_timestamp >= 1 or self.training is True:
            self.raw_position = state["paddle2"]["y"] * 1000
            self.game_state = await self.convert_state(state)
            self.update_timestamp = time.time()
        # logging.info(f"Game state: {self.game_state}, raw position: {self.raw_position}, next collision: {self.next_collision}, pause: {self.pause}")
        result = await self.global_ai.get_action(self.game_state, self.raw_position,
                                                  self.next_collision, self.pause)
        
        # if result != 'still':
        #     logging.info(f"AI result: {result}\n\n\n")
        
        if self.difficulty == 1 and result != 'still':
            if random.choice([0, 1, 2]) == 1:
                result = 'still'
            
        if result == 'up':
            # for _ in range(10):
            for _ in range(5):
                self.raw_position = self.raw_position - 3
                if self.raw_position < self.min_position:
                    self.raw_position = self.min_position
        elif result == 'down':
            # for _ in range(10):
            for _ in range(5):
                self.raw_position = self.raw_position + 3
                if self.raw_position > self.max_position:
                    self.raw_position = self.max_position

        # await self.compare_positions(state, self.raw_position, self.side, result)
        return result
    

    # async def compare_positions(self, state, raw_position, side, result):
        if result == 'up':
            if side == "right":
                new_pos = (state["paddle2"]["y"] * 1000) + (5 * (self.global_ai.ai.win_height / 333))
                if raw_position != new_pos:
                    logging.info(f"compare_positions: Error in position: {raw_position}, new_pos: {new_pos}\n\n")
            else:
                if round(raw_position) != round(state["paddle1"]["y"] * 1000):
                    logging.info(f"Error in position: {raw_position}, state position: {state['paddle1']['y'] * 1000}\n\n")
        elif result == 'down':
            if side == "right":
                if round(raw_position) != round(state["paddle2"]["y"] * 1000):
                    logging.info(f"Error in position: {raw_position}, state position: {state['paddle2']['y'] * 1000}\n\n")
            else:
                if round(raw_position) != round(state["paddle1"]["y"] * 1000):
                    logging.info(f"Error in position: {raw_position}, state position: {state['paddle1']['y'] * 1000}\n\n")

    async def convert_state(self, state) -> list:

        # logging.info(f"Converting state: {state}")

        res = []


        # res.append(round(state["ball"]["x"], 1))
        # res.append(round(state["ball"]["y"], 1))
        # res.append(round(state["ball"]["rounded_angle"], 1))
        # if self.side == "right":
        #     res.append(round(state["paddle2"]["y"], 1))
        # else:
        #     res.append(round(state["paddle1"]["y"], 1))

        res.append(await self.round_value(state["ball"]["x"]))
        res.append(await self.round_value(state["ball"]["y"]))
        res.append(await self.round_value(state["ball"]["rounded_angle"]))
        if self.side == "right":
            res.append(await self.round_value(state["paddle2"]["y"]))
        else:
            res.append(await self.round_value(state["paddle1"]["y"]))

        coll = []
        coll.append(state["game"]["ai_data"][4][0])
        coll.append(state["ball"]["next_collision"][1])

        res.append(coll)
        #
        # if self.difficulty == 1:
        #     res[0] += round(random.uniform(-0.3, 0.3),1)
        #     res[1] += round(random.uniform(-0.3, 0.3),1)
        #     res[2] += round(random.uniform(-0.3, 0.3),1)
        # res[4][1] = round(res[4][1] / self.win_height, 1)

        self.next_collision = res.pop()
        if self.difficulty == 1 and self.training is False:
            self.next_collision[1] += random.uniform(-50, 50)
            
        # logging.info(f"Converted state: {res}")
        return res

    async def round_value(self, nb):
        #round nb to 0.05
        return round(nb * 20) / 20

class AIService:
    def __init__(self):
        # Initialisation des modèles globaux avec vos paramètres actuels
        self.global_models = {
            'easy': GlobalAI(1500, 1000, 6, 166, 1, "right"),
            'medium': GlobalAI(1500, 1000, 6, 166, 2, "right"),
            'hard': GlobalAI(1500, 1000, 6, 166, 3, "right"),
            'easy_p1': GlobalAI(1500, 1000, 6, 166, 1, "left"),
            'medium_p1': GlobalAI(1500, 1000, 6, 166, 2, "left"),
            'hard_p1': GlobalAI(1500, 1000, 6, 166, 3, "left")
        }

        self.game_instances = {}

    def add_game_instance(self, uid: str):
        difficulty = self._get_difficulty_from_uid(uid)
        # logging.info(f"Adding game instance for {uid} with difficulty {difficulty}")
        global_ai = self.global_models[difficulty]
        self.game_instances[uid] = {'ai': GameAgent(global_ai)}

    def _get_difficulty_from_uid(self, uid: str) -> str:
        if uid[0] == '1':
            return 'easy_p1' if uid[-1] == '1' else 'easy'
        elif uid[0] == '2':
            return 'medium_p1' if uid[-1] == '1' else 'medium'
        else:
            return 'hard_p1' if uid[-1] == '1' else 'hard'

    async def process_and_send_action(self, websocket, event, uid):
        try:
            if uid in self.game_instances:
                action = await self.game_instances[uid]['ai'].get_action(event)
                if action == "Error":
                    await self.cleanup_ai_instance(uid)
                    return
                
                elif action == 'wait':
                    logging.info(f"Waiting for action for game {uid}\n\n\n")
                    return

                await websocket.send(json.dumps({
                    "type": "move",
                    "direction": str(action),
                    'sender': 'AI'
                }))
        except Exception as e:
            logging.error(f"Error processing action for game {uid}: {e}")
            await self.cleanup_ai_instance(uid)

    async def cleanup_ai_instance(self, uid: str):
        if uid in self.game_instances:
            del self.game_instances[uid]
            logging.info(f"Cleaned up AI instance for game {uid}")

    async def listen_for_messages(self, websocket, game_uid):
        try:
            while True:
                try:
                    message = await websocket.recv()
                    event = json.loads(message)
                    if event["type"] == "setup":
                        await websocket.send(json.dumps({
                            'type': 'setup',
                            'sender': 'AI'
                        }))
                    elif event["type"] == "None":
                        await self.process_and_send_action(websocket, event, game_uid)
                    elif event["type"] == "gameover":
                        logging.info(f"AI: Game over for game {game_uid}")
                        await self.cleanup_ai_instance(game_uid)
                        return
                    await asyncio.sleep(0.001)
                except asyncio.TimeoutError:
                    continue
        except websockets.exceptions.ConnectionClosedError:
            print(f"Connection closed for game {game_uid}")
            await self.cleanup_ai_instance(game_uid)
            return

    async def join_game(self, uid: str):
        uri = f"wss://nginx:7777/ws/pong/{uid}/"
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(uri, ssl=ssl_context) as websocket:
                print(f"IA connectée à la partie {uid}")
                await websocket.send(json.dumps({
                    "type": "greetings",
                    "sender": "AI"
                }))
                await self.listen_for_messages(websocket, uid)
        except Exception as e:
            logging.error(f"Error in join_game for {uid}: {e}")
            await self.cleanup_ai_instance(uid)

    async def continuous_listen_for_uid(self):
        while True:
            try:
                response = requests.get(
                    "https://nginx:7777/game/join/?mode=AI",
                    verify=False
                )
                if response.status_code == 200:
                    data = response.json()
                    # logging.info(f"Checking for new game: {data}")
                    if data.get('uid') != 'error':
                        uid = data['uid']
                        if uid not in self.game_instances:
                            self.add_game_instance(uid)
                            asyncio.create_task(self.join_game(uid))
                            logging.info(f"Joining new game: {uid}")
            except Exception as e:
                logging.error(f"Error in continuous_listen_for_uid: {e}")

            await asyncio.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    ai_service = AIService()
    asyncio.run(ai_service.continuous_listen_for_uid())