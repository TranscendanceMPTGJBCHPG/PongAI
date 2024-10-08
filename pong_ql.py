import numpy as np
import pickle
import random
import time

class QL_AI:
    
    def __init__(self, width, height, paddle_width, paddle_height, difficulty, side) -> None:

        self.side = side

        self.raw_position = None
        self.win_width = width
        self.win_height = height
        self.paddle_height = paddle_height
        self.paddle_width = paddle_width

        self.alpha = 0.4
        self.gamma = 0.7
        self.epsilon_decay = 0.0001 #baisse du taux d'apprentissage au fur et a mesure du jeu
        self.epsilon_min = 0.01

        self.difficulty = difficulty
        if self.side == "left":
            self.training = True
            self.saving = True
            self.loading = False
        self.training = False
        self.saving = False
        self.loading = True

        if self.training == True:
            if self.loading == True:
                self.epsilon = 0.5
            else:
                self.epsilon = 1 # 1 = uniquement exploration
        else:
            self.epsilon = 0
        self.qtable = {}
        self.rewards = []
        self.episodes = []
        self.average = []
        self.name = "Test"
        self.state = None
        self.last_state_timestamp = 0
        self.nextCollision = None

        self.counter = 0

        if self.loading is True:
            self.init_ai_modes()


    def fromDict(self, data):
        self.win_width = data["width"]
        self.win_height = data["height"]
        self.paddle_height = data["paddle_height"]
        self.paddle_width = data["paddle_width"]
        self.difficulty = data["difficulty"]
        self.loading = data["loading"]
        self.init_ai_modes()


    def init_ai_modes(self):
        if self.loading == True:
            if self.difficulty == 3:
                if self.side == "right":
                    self.load("/app/ai_data/AI_hard.pkl")
                else:
                    self.load("/app/ai_data/AI_hard_p1.pkl")
            elif self.difficulty == 2:
                if self.side == "right":
                    self.load("/app/ai_data/AI_medium.pkl")
                else:
                    self.load("/app/ai_data/AI_medium_p1.pkl")
            elif self.difficulty == 1:
                if self.side == "right":
                    self.load("/app/ai_data/AI_easy.pkl")
                else:
                    self.load("/app/ai_data/AI_easy_p1.pkl")

    def epsilon_greedy(self):
        if self.epsilon == self.epsilon_min:
            return
        self.epsilon -= self.epsilon_decay
        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min
    

    def getClosestState(self, state):
        closest_state = None
        previous_state = None
        for s in self.qtable.keys():
            if closest_state == None:
                closest_state = s
            else:
                previous_state = closest_state
                closest_state = s
                if previous_state < state and closest_state > state:
                    return closest_state
        return closest_state


    def convert_state(self, state) -> list:
        res = []

        current_timestamp = time.time()
        # print(f"current timestamp: {current_timestamp}, last timestamp: {self.last_state_timestamp}")

        self.raw_position = state["paddle2"]["y"]

        if current_timestamp - self.last_state_timestamp < 1 and self.training == False:
            self.state[3] = round(self.raw_position, 1)
            # if self.difficulty == 1:
                # self.state[3] += round(random.uniform(-0.2, 0.2)
            return self.state
        self.last_state_timestamp = current_timestamp

        res.append(round(state["ball"]["x"], 1))
        res.append(round(state["ball"]["y"], 1))
        res.append(round(state["ball"]["rounded_angle"], 1))
        res.append(round(state["paddle2"]["y"], 1))

        coll = []
        coll.append(state["game"]["ai_data"][4][0])
        coll.append(state["ball"]["next_collision"][1])

        # print(f"coll: {coll}")

        res.append(coll)

        # print(f"after appending state: {res}")

        #nerfing AI accuracy for easy mode
        if self.difficulty == 1:
            res[0] += round(random.uniform(-0.3, 0.3),1)
            res[1] += round(random.uniform(-0.3, 0.3),1)
            res[2] += round(random.uniform(-0.3, 0.3),1)
            # res[4][1] += random.randint(-20, 20)
        res[4][1] = round(res[4][1] / self.win_height, 1)

        self.nextCollision = res.pop()

        # print(f"after pop, self.nextCollision: {self.nextCollision}")
        #
        # print(f"converted state: {res}")

        if self.nextCollision[0] == 0:
            return self.ball_is_moving_away(res)
    
        return res
    

    def ball_is_moving_away(self, state):
        res = []

        res.append(state[1])
        res.append(state[3])

        return res
    

    def handle_pause(self, state):
        paddle_position = state["paddle2"]["y"]
        if paddle_position > 0.52:
            return "up"
        elif paddle_position < 0.48:
            return "down"
        return "still"


    async def getAction(self, initial_state):

        # print(f"in get action, state = {initial_state}")
        # print(f"difficulty: {self.difficulty}")

        self.state = self.convert_state(initial_state)

        paddle_pos_from_0_to_1 = self.state[3]

        # print(f"paddle_pos_from_0_to_1: {paddle_pos_from_0_to_1}")

        if initial_state['game']['pause'] == True:
            return self.handle_pause(initial_state)
        #get last element of the list state
        stateRepr = repr(self.state)
        # print(f"stateRepr: {stateRepr}")

        if stateRepr not in self.qtable:
            self.qtable[stateRepr] = np.zeros(3)
        self.epsilon_greedy()
        if self.training == True:
            if np.random.uniform() < self.epsilon:
                action = np.random.choice(3)
            else:
                action = np.argmax(self.qtable[stateRepr])
        else:
            action = np.argmax(self.qtable[stateRepr])

        reward = self.getReward(self.nextCollision, action, self.state[3], self.difficulty)
        self.upadateQTable(repr(self.state), action, reward, repr(self.state))

        # print(f"qtable size: {len(self.qtable)}")
        if (len(self.qtable) >= 8000) and self.saving == True:
            await self.save_wrapper()
            exit()
        self.counter += 1
        if self.counter == 100:
            await self.save_wrapper()
            self.counter = 0
            # print("\n\n\n\nsaved\n\n\n\n")
            
        if action == 1:
            return "up"
        elif action == 2:
            return "down"
        return "still"
    

    async def save_wrapper(self):
        if self.saving is True:
            if self.difficulty == 3:
                await self.save("hard")
            elif self.difficulty == 2:
                await self.save("medium")
            elif self.difficulty == 1:
                await self.save("easy")


    def calculateNextState(self, state, action):
        nextState = state.copy()
        if action == 1:
            nextState[3] += 1
        elif action == 2:
            nextState[3] -= 1
        return nextState
    

    def upadateQTable(self, state, action, reward, nextState):

        # print(f"in update qtable, state: {state}, nextState: {nextState}")
        if nextState not in self.qtable:
            self.qtable[nextState] = np.zeros(3)
        tdTarget = reward + self.gamma * np.max(self.qtable[nextState])
        tdError = tdTarget - self.qtable[state][action]
        self.qtable[state][action] += self.alpha * tdError


    def determine_collision(self, next_collision, paddle_position):

        security_margin = 5 / self.win_height
        margin_from_middle = self.paddle_height / 2 / self.win_height - security_margin

        # print(f"security margin: {security_margin}, margin from middle: {margin_from_middle}")

        top_paddle = round(paddle_position - security_margin, 2)
        bottom_paddle = round(paddle_position + security_margin, 2)

        # print(f"got in determine collision, next_collision: {next_collision}, paddle_position: {paddle_position}")
        # print(f"bottom_paddle: {bottom_paddle}, top_paddle: {top_paddle}")
        if next_collision > bottom_paddle:
            # print("collision will be below paddle")
            return 1
        elif next_collision < top_paddle:
            # print("collision will be above paddle")
            return -1
        return 0


    def getReward(self, nextCollision, action, previousPosition, difficulty):

        up = 1
        down = 2
        still = 0

        maxReward = 10
        minReward = -10
        result:int = 0

        # print(f"nextCollision: {nextCollision}, action: {action}, previousPosition: {previousPosition}, difficulty: {difficulty}")

        relative_collision = self.determine_collision(nextCollision[1], previousPosition)

        # print(f"in reward next collision: {nextCollision}")

        # if self.difficulty == 1:
        #     nextCollision[1] += random.randint(-5, 5)
        if nextCollision[0] == 1:
            if action == up:
                if relative_collision == -1:
                    result = maxReward
                else:
                    result = minReward
            elif action == down:
                if relative_collision == 1:
                    result = maxReward
                else:
                    result = minReward
            elif action == still:
                if relative_collision == 0:
                    result = maxReward
                else:
                    result = minReward
        else:
            if self.difficulty == 3:
                if action == up and nextCollision[1] < previousPosition and previousPosition > 0.25:
                    result = maxReward
                elif action == down and nextCollision[1] > previousPosition and previousPosition < 0.75:
                    result = maxReward
                elif action == still and abs(nextCollision[1] - previousPosition) < self.paddle_height / 1000 and previousPosition > self.win_height // 4 // 1000 and previousPosition < 0.75:
                    result = maxReward
                else:
                    result = minReward
            else:
                # print(f"difficulty = {self.difficulty}")
                if action == up or action == down:
                    result = minReward
                else:
                    result = maxReward
        # print(f"reward: {result}")
        return result


    async def save(self, name):

        import os
        if self.side == "right":
            file_path = f"/app/ai_data/AI_{name}.pkl"
        else:
            file_path = f"app/ai_data/AI_{name}_left.pkl"

        try:
            #save qtable in ai_data directory
            with open(file_path, 'wb') as file:
                # print(f"saved at {file}")
                pickle.dump(self.qtable, file)
                # print("saved")
                # file.close()
        except Exception as e:
            print(f"Error in save: {e}")
            file.close()


    def load(self, name):
        import os
        if not os.path.exists(name):
            print(f"Le fichier {name} n'existe pas.")
            return None

        if os.path.getsize(name) == 0:
            print(f"Le fichier {name} est vide.")
            return None
        
        try:
            with open(name, 'rb') as file:
                self.qtable = pickle.load(file)
                # file.close()

        except Exception as e:
            print(f"Error in load: {e}")
            # file.close()
            return None



        
