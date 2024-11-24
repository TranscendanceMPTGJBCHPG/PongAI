import numpy as np
import pickle
import random
import time
import logging
import hashlib
from pathlib import Path
import os
import threading


class QTableManager:
    def __init__(self, base_path="/app/ai_data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        # logging.info(f"SecureQTableManager initialisé avec le chemin de base: {self.base_path}")

    def _get_file_paths(self, name, side):
        safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
        suffix = "_left" if side == "left" else ""
        pkl_path = self.base_path / f"AI_{safe_name}{suffix}.pkl"
        hash_path = self.base_path / f"AI_{safe_name}{suffix}.hash"
        # logging.debug(f"Chemins générés - PKL: {pkl_path}, Hash: {hash_path}")
        return pkl_path, hash_path

    def _calculate_hash(self, data):
        """Calcule le hash SHA-256 des données"""
        hash_value = hashlib.sha256(pickle.dumps(data)).hexdigest()
        # logging.debug(f"Hash calculé: {hash_value[:10]}...")
        return hash_value

    def _create_empty_qtable(self):
        """Crée une nouvelle Q-table vide"""
        return {}

    async def save(self, qtable, name, side="right"):
        with self.lock:
            pkl_path, hash_path = self._get_file_paths(name, side)
            temp_pkl = pkl_path.with_suffix('.tmp')
            temp_hash = hash_path.with_suffix('.tmp')

            try:
                # logging.info(f"Début de la sauvegarde - Fichier PKL: {pkl_path}")

                if hasattr(os, 'statvfs'):
                    stats = os.statvfs(self.base_path)
                    free_space = stats.f_frsize * stats.f_bfree
                    data_size = len(pickle.dumps(qtable))
                    if data_size > free_space:
                        logging.error("Espace disque insuffisant")
                        return False

                hash_value = self._calculate_hash(qtable)

                with open(temp_pkl, 'wb') as f:
                    pickle.dump(qtable, f)
                    # logging.debug(f"Données sauvegardées dans {temp_pkl}")

                with open(temp_hash, 'w') as f:
                    f.write(hash_value)
                    # logging.debug(f"Hash sauvegardé dans {temp_hash}")

                temp_pkl.rename(pkl_path)
                temp_hash.rename(hash_path)

                # logging.info(f"Sauvegarde réussie - PKL: {pkl_path}, Hash: {hash_path}")
                return True

            except Exception as e:
                logging.error(f"Erreur lors de la sauvegarde: {e}")
                for temp_file in [temp_pkl, temp_hash]:
                    if temp_file.exists():
                        temp_file.unlink()
                return False

    def load(self, name, side="right"):
        with self.lock:
            pkl_path, hash_path = self._get_file_paths(name, side)

            try:
                logging.info(f"Tentative de chargement - PKL: {pkl_path}")

                if not pkl_path.exists():
                    logging.info(f"Fichier PKL non trouvé: {pkl_path}")
                    return self._create_empty_qtable()

                if pkl_path.stat().st_size == 0:
                    logging.warning(f"Fichier PKL vide: {pkl_path}")
                    return self._create_empty_qtable()

                with open(pkl_path, 'rb') as f:
                    qtable = pickle.load(f)

                if hash_path.exists():
                    with open(hash_path, 'r') as f:
                        stored_hash = f.read().strip()
                        current_hash = self._calculate_hash(qtable)

                        if stored_hash != current_hash:
                            logging.error(f"""
                            Intégrité compromise pour {pkl_path}
                            Hash stocké: {stored_hash[:10]}...
                            Hash calculé: {current_hash[:10]}...
                            """)
                            return self._create_empty_qtable()
                else:
                    logging.warning(f"Fichier hash non trouvé: {hash_path}")
                    hash_value = self._calculate_hash(qtable)
                    with open(hash_path, 'w') as f:
                        f.write(hash_value)
                    logging.info(f"Nouveau fichier hash créé: {hash_path}")

                logging.info(f"Chargement réussi - PKL: {pkl_path}")
                return qtable

            except Exception as e:
                logging.error(f"Erreur lors du chargement: {e}")
                return self._create_empty_qtable()

class QL_AI:
    
    def __init__(self, width, height, paddle_width, paddle_height, difficulty, side) -> None:

        self.side = side

        self.win_width = width
        self.win_height = height
        self.paddle_height = paddle_height
        self.paddle_width = paddle_width

        self.alpha = 0.4
        self.gamma = 0.7
        self.epsilon_decay = 0.0001
        self.epsilon_min = 0.01

        self.difficulty = difficulty
        self.qtable = {}
        self.qtable_manager = QTableManager()

        self.counter = 0

        self.loading = True
        self.training = False
        self.saving = False
        self.epsilon = self.epsilon_min

        # self.loading = False
        # self.training = True
        # self.saving = False
        # self.epsilon = 1

        if self.loading is True:
            self.init_ai_modes()

    def init_ai_modes(self):
        if self.loading:
            difficulty_map = {
                3: "hard",
                2: "medium",
                1: "easy"
            }
            name = difficulty_map.get(self.difficulty)
            if name:
                loaded_qtable = self.qtable_manager.load(name, self.side)
                if loaded_qtable is not None:
                    self.qtable = loaded_qtable


    def epsilon_greedy(self):
        if self.epsilon == self.epsilon_min:
            return
        self.epsilon -= self.epsilon_decay
        if self.epsilon < self.epsilon_min:
            self.epsilon = self.epsilon_min
    

    def handle_pause(self, raw_pos):
        relativ_pos = raw_pos / self.win_height
        if relativ_pos > 0.52:
            return "up"
        elif relativ_pos < 0.48:
            return "down"
        return "still"


    async def getAction(self, state:list, raw_pos:int, next_collision:list, pause:bool) -> str :

        if pause is True:
            return self.handle_pause(raw_pos)
        
        stateRepr = repr(state)

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



        reward = self.getReward(next_collision, action, raw_pos, self.difficulty)
        self.upadateQTable(repr(state), action, reward, repr(state))
            
        if action == 1:
            return "up"
        elif action == 2:
            return "down"
        return "still"
    

    async def save_wrapper(self):
        if self.saving:
            difficulty_map = {
                3: "hard",
                2: "medium",
                1: "easy"
            }
            name = difficulty_map.get(self.difficulty)
            if name:
                await self.qtable_manager.save(self.qtable, name, self.side)
    

    def upadateQTable(self, state, action, reward, nextState):
        if nextState not in self.qtable:
            self.qtable[nextState] = np.zeros(3)
        tdTarget = reward + self.gamma * np.max(self.qtable[nextState])
        tdError = tdTarget - self.qtable[state][action]
        self.qtable[state][action] += self.alpha * tdError


    def determine_collision(self, next_collision, paddle_position):

        security_margin = 5

        top_paddle = paddle_position - self.paddle_height / 2 + security_margin
        bottom_paddle = paddle_position + self.paddle_height / 2 - security_margin

        if next_collision > bottom_paddle:
            return 1
        elif next_collision < top_paddle:
            return -1
        else:
            return 0


    def getReward(self, nextCollision, action, previousPosition, difficulty):

        up = 1
        down = 2
        still = 0

        maxReward = 10
        minReward = -10
        result:int = 0

        relative_collision = self.determine_collision(nextCollision[1], previousPosition)

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
            else:
                if action == up or action == down:
                    result = minReward
                else:
                    result = maxReward
        return result


    async def save(self, name):

        import os
        if self.side == "right":
            file_path = f"/app/ai_data/AI_{name}.pkl"
        else:
            file_path = f"/app/ai_data/AI_{name}_left.pkl"

        try:
            with open(file_path, 'wb') as file:
                pickle.dump(self.qtable, file)
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

        except Exception as e:
            print(f"Error in load: {e}")
            return None



        
