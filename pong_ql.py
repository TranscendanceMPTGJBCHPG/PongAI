import numpy as np
import pickle
import random
import time
import logging

class QL_AI:
    
    def __init__(self, width, height, paddle_width, paddle_height, difficulty, side) -> None:

        self.side = side

        # self.raw_position = None
        self.win_width = width
        self.win_height = height
        self.paddle_height = paddle_height
        self.paddle_width = paddle_width

        self.alpha = 0.4
        self.gamma = 0.7
        self.epsilon_decay = 0.0001 #baisse du taux d'apprentissage au fur et a mesure du jeu
        self.epsilon_min = 0.01

        self.difficulty = difficulty
        self.qtable = {}
        self.rewards = []
        self.episodes = []
        self.average = []
        self.name = ""
        self.state = None
        self.last_state_timestamp = 0
        # self.nextCollision = None

        self.counter = 0

        # self.loading = True
        # self.training = False
        # self.saving = False
        # self.epsilon = self.epsilon_min

        self.loading = False
        self.training = True
        self.saving = True
        self.epsilon = 1

        if self.loading is True:
            self.init_ai_modes()

        print(f"AI: {self.difficulty}, side: {self.side}, training: {self.training}, saving: {self.saving}, epsilon: {self.epsilon}, loading: {self.loading}, qtable size: {len(self.qtable)}")

    def init_ai_modes(self):
        if self.loading == True:
            if self.difficulty == 3:
                if self.side == "right":
                    self.load("/app/ai_data/AI_hard.pkl")
                else:
                    self.load("/app/ai_data/AI_hard_left.pkl")
                    print("loaded hard AI Player 1")
            elif self.difficulty == 2:
                if self.side == "right":
                    self.load("/app/ai_data/AI_medium.pkl")
                else:
                    self.load("/app/ai_data/AI_medium_left.pkl")
            elif self.difficulty == 1:
                if self.side == "right":
                    self.load("/app/ai_data/AI_easy.pkl")
                else:
                    self.load("/app/ai_data/AI_easy_left.pkl")

    def epsilon_greedy(self):
        if self.epsilon == self.epsilon_min:
            return
        self.epsilon -= self.epsilon_decay
        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min
    

    def ball_is_moving_away(self, state):
        if self.state is None:
            return state
        res = []

        res.append(state[1])
        res.append(state[3])

        return res
    

    def handle_pause(self, raw_pos):
        relativ_pos = raw_pos / self.win_height
        if relativ_pos > 0.52:
            return "up"
        elif relativ_pos < 0.48:
            return "down"
        return "still"


    async def getAction(self, state:list, raw_pos:int, next_collision:list, pause:bool) -> str :

        # logging.info(f"in AI\n\nstate: {state}, raw_pos: {raw_pos}, next_collision: {next_collision}, pause: {pause}")
        if pause is True:
            return self.handle_pause(raw_pos)
        #get last element of the list state
        stateRepr = repr(state)
        # print(f"stateRepr: {stateRepr}")

        if stateRepr not in self.qtable:
            print(f"new STATE\n")
            self.qtable[stateRepr] = np.zeros(3)
        self.epsilon_greedy()
        if self.training == True:
            if np.random.uniform() < self.epsilon:
                action = np.random.choice(3)
            else:
                action = np.argmax(self.qtable[stateRepr])
        else:
            action = np.argmax(self.qtable[stateRepr])



        reward = self.getReward(next_collision, action, raw_pos, self.difficulty)
        self.upadateQTable(repr(state), action, reward, repr(state))

        print(f"qtable size: {len(self.qtable)}")
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

        # logging.info(f"in determine collision, next_collision: {next_collision}, paddle_position: {paddle_position}")

        security_margin = 5
        # margin_from_middle = self.paddle_height / 2 / self.win_height - security_margin

        # print(f"security margin: {security_margin}, margin from middle: {margin_from_middle}")

        top_paddle = paddle_position - self.paddle_height / 2 + security_margin
        bottom_paddle = paddle_position + self.paddle_height / 2 - security_margin

        print(f"got in determine collision, next_collision: {next_collision}, paddle_position: {paddle_position}, paddle_height: {self.paddle_height}")
        print(f"bottom_paddle: {bottom_paddle}, top_paddle: {top_paddle}")

        if next_collision > bottom_paddle:
            logging.info("collision will be below paddle")
            return 1
        elif next_collision < top_paddle:
            logging.info("collision will be above paddle")
            return -1
        else:
            logging.info("collision will be on paddle")
        return 0


    def getReward(self, nextCollision, action, previousPosition, difficulty):

        up = 1
        down = 2
        still = 0

        maxReward = 10
        minReward = -10
        result:int = 0

        print(f"nextCollision: {nextCollision}, action: {action}, previousPosition: {previousPosition}, difficulty: {difficulty}")

        relative_collision = self.determine_collision(nextCollision[1], previousPosition)

        # print(f"in reward next collision: {nextCollision}")

        # if self.difficulty == 1:
        #     nextCollision[1] += random.randint(-5, 5)


        #ball is moving towards the paddle
        if nextCollision[0] == 1 and self.side == "right" or nextCollision[0] != 1  and self.side == "left":
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

                if action == up:
                    if relative_collision == -1 and previousPosition > 0.33 * self.win_height:
                        result = maxReward
                    else:
                        result = minReward
                elif action == down:
                    if relative_collision == 1 and previousPosition < 0.66 * self.win_height:
                        result = maxReward
                    else:
                        result = minReward
                elif action == still:
                    if relative_collision == 0 and previousPosition > 0.33 * self.win_height and previousPosition < 0.66 * self.win_height:
                        result = maxReward
                    else:
                        result = minReward


                # if relative_collision == -1:
                #     result = maxReward
                # elif action == down and nextCollision[1] > previousPosition and previousPosition < 0.75 * self.win_height:
                #     result = maxReward
                # elif action == still and relative_collision == 0:
                #     result = maxReward
                # else:
                #     result = minReward
            else:
                # print(f"difficulty = {self.difficulty}")
                if action == up or action == down:
                    result = minReward
                else:
                    result = maxReward
        print(f"reward: {result}")
        return result


    async def save(self, name):

        import os
        if self.side == "right":
            file_path = f"/app/ai_data/AI_{name}.pkl"
        else:
            file_path = f"/app/ai_data/AI_{name}_left.pkl"

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



        
