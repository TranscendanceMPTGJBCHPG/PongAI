import numpy as np
import pickle
import random

class QL_AI:
    
    def __init__(self, width, height, paddle_width, paddle_height, difficulty) -> None:
        self.win_width = width
        self.training = True
        self.win_height = height
        self.paddle_height = paddle_height
        self.paddle_width = paddle_width
        self.alpha = 0.4
        self.gamma = 0.7
        self.epsilon_decay = 0.00001 #baisse du taux d'apprentissage au fur et a mesure du jeu
        self.epsilon_min = 0.01
        self.epsilon = 1 # 1 = uniquement exploration
        self.qtable = {}
        self.rewards = []
        self.episodes = []
        self.average = []
        self.name = "Test"
        self.loading = False
        self.difficulty = 3
        # self.load(f"AI_{difficulty}.pkl")

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
                self.load("AI_hard.pkl")
                print("hard AI loaded")
            elif self.difficulty == 2:
                self.load("AI_medium.pkl")
            elif self.difficulty == 1:
                self.load("AI_easy.pkl")



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

    def convert_state(self, state):
        res = []
    
        res.append(self.round_to_nearest_5_cent(state["ball"]["x"]))
        res.append(self.round_to_nearest_5_cent(state["ball"]["y"]))
        res.append(state["ball"]["rounded_angle"])
        res.append(self.round_to_nearest_5_cent(state["paddle2"]["y"] + ((self.paddle_height / 2) / self.win_height)))
        res.append(state["ball"]["next_collision"])
        res[4][1] = round(res[4][1] / self.win_height, 2)
    
        print(f"converted state: {res}")
    
        return res
    
    def round_to_nearest_5_cent(self, value):
        value_in_cents = value * 100
        rounded_value_in_cents = round(value_in_cents / 5) * 5
        return rounded_value_in_cents / 100
    
    def handle_pause(self, state):
        paddle_position = state[3]
        if paddle_position > 0.52:
            return "up"
        elif paddle_position < 0.48:
            return "down"
        return "still"


    def getAction(self, initial_state):

        print(f"in get action, state = {initial_state}")

        state = self.convert_state(initial_state)

        paddle_pos_from_0_to_1 = state[3]

        print(f"paddle_pos_from_0_to_1: {paddle_pos_from_0_to_1}")

        if initial_state['game']['pause'] == True:
            return self.handle_pause(initial_state)
        
        nextCollision = state.pop()
        stateRepr = repr(state)
        print(f"stateRepr: {stateRepr}")

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
        # print(f"qtaable size: {len(self.qtable)}")
        # nextState = self.calculateNextState(state, action)
        reward = self.getReward(nextCollision, action, state[3], self.difficulty)
        self.upadateQTable(repr(state), action, reward, repr(state))
        if action == 1:
            return "up"
        elif action == 2:
            return "down"
        return "still"

    def calculateNextState(self, state, action):
        nextState = state.copy()
        if action == 1:
            nextState[3] += 1
        elif action == 2:
            nextState[3] -= 1
        return nextState
    

    def upadateQTable(self, state, action, reward, nextState):

        print(f"in update qtable, state: {state}, nextState: {nextState}")
        if nextState not in self.qtable:
            self.qtable[nextState] = np.zeros(3)
        tdTarget = reward + self.gamma * np.max(self.qtable[nextState])
        tdError = tdTarget - self.qtable[state][action]
        self.qtable[state][action] += self.alpha * tdError

    def determine_collision(self, next_collision, paddle_position):
        #calculate bottom - 5 of paddle in percentage of window height

        #0.5 + ((166 / 2 + 5) / 1000)
        #calculate top - 5 of paddle in percentage of window height
        security_margin = 5 / self.win_height
        margin_from_middle = self.paddle_height / 2 / self.win_height - security_margin

        print(f"security margin: {security_margin}, margin from middle: {margin_from_middle}")

        top_paddle = round(paddle_position - security_margin, 2)
        bottom_paddle = round(paddle_position + security_margin, 2)

        print(f"got in determine collision, next_collision: {next_collision}, paddle_position: {paddle_position}")
        print(f"bottom_paddle: {bottom_paddle}, top_paddle: {top_paddle}")
        if next_collision > bottom_paddle:
            print("collision will be below paddle")
            return 1
        elif next_collision < top_paddle:
            print("collision will be above paddle")
            return -1
        return 0


    def getReward(self, nextCollision, action, previousPosition, difficulty):

        up = 1
        down = 2
        still = 0

        maxReward = 10
        minReward = -10
        result:int = 0

        print(f"nextCollision: {nextCollision}, action: {action}, previousPosition: {previousPosition}, difficulty: {difficulty}")

        # 0 = collision on paddle, 1 = collision below paddle, -1 = collision above paddle
        relative_collision = self.determine_collision(nextCollision[1], previousPosition)

        if difficulty == 1:
            nextCollision[1] += random.randint(-5, 5)
        if nextCollision[0] == 1:
            # paddle_position = previousPosition + (self.paddle_height // 2 // self.win_height)
            #calculate the size of the paddle reltive to the window
            # print(self.paddle_height // 2 // self.win_height)
            # print(f"paddle_position: {paddle_position}")
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
            if difficulty == 3:
                if action == up and nextCollision[1] < previousPosition and previousPosition > 0.25:
                    result = maxReward
                elif action == down and nextCollision[1] > previousPosition and previousPosition < 0.75:
                    result = maxReward
                elif action == still and abs(nextCollision[1] - previousPosition) < self.paddle_height / 1000 and previousPosition > self.win_height // 4 // 1000 and previousPosition < 0.75:
                    result = maxReward
                else:
                    result = minReward
            else:
                if action == up or action == down:
                    result = minReward
                else:
                    result = maxReward
        print(f"reward: {result}")
        return result
     
    def save(self, name):
        with open(f"AI_{name}.pkl", 'wb') as file:
            pickle.dump(self.qtable, file)

    def load(self, name):
        with open(name, 'rb') as file:
            self.qtable = pickle.load(file)



        
