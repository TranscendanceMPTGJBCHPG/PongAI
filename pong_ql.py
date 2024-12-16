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
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            os.chmod(self.base_path, 0o775)

            # Récupération de la clé secrète
            self.secret = os.getenv('AI_HASH_SECRET')
            # logging.info(f"secret: {self.secret}")
            if not self.secret:
                logging.error("HASH_SECRET non définie! Utilisation d'une clé par défaut non sécurisée")
                self.secret = "default_secret_key_not_secure"

            # logging.info(f"SecureQTableManager initialisé - Chemin: {self.base_path}")
        except Exception as e:
            logging.error(f"Erreur d'initialisation: {e}")
        self.lock = threading.Lock()

    def _get_file_paths(self, name, side):
        """Génère les chemins des fichiers de manière sécurisée"""
        safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
        suffix = "_left" if side == "left" else ""
        pkl_path = self.base_path / f"AI_{safe_name}{suffix}.pkl"
        hash_path = self.base_path / f"AI_{safe_name}{suffix}.hash"
        return pkl_path, hash_path

    def _convert_numpy_arrays(self, data):
        """Convertit les arrays numpy en listes Python"""
        if isinstance(data, dict):
            return {k: v.tolist() if hasattr(v, 'tolist') else v for k, v in data.items()}
        return data

    def _calculate_hash(self, data):
        """Calcule le hash SHA-256 avec la clé secrète"""
        # Convertir les arrays numpy en listes
        data = self._convert_numpy_arrays(data)

        # logging.info(f"Type des données après conversion: {type(data)}")
        if isinstance(data, dict):
            # logging.info(f"Taille du dictionnaire: {len(data)}")
            first_item = next(iter(data.items())) if data else None
            # logging.info(f"Premier élément du dictionnaire après conversion: {first_item}")

        secret_bytes = self.secret.encode('utf-8')

        if isinstance(data, dict):
            from collections import OrderedDict
            data = OrderedDict(sorted(data.items()))

        data_bytes = pickle.dumps(data, protocol=2)

        return hashlib.sha256(secret_bytes + data_bytes).hexdigest()

    def _create_empty_qtable(self):
        """Crée une nouvelle Q-table vide"""
        return {}

    def load(self, name, side="right"):
        with self.lock:
            pkl_path, hash_path = self._get_file_paths(name, side)

            try:
                # Cas 1: Fichier inexistant ou vide
                if not pkl_path.exists() or pkl_path.stat().st_size == 0:
                    # logging.info(f"Création d'une nouvelle Q-table (fichier absent ou vide): {pkl_path}")
                    return self._create_empty_qtable()

                # Cas 2: Fichier existe avec des données
                with open(pkl_path, 'rb') as f:
                    qtable = pickle.load(f)

                # Vérification du hash
                if not hash_path.exists():
                    # logging.warning(f"Hash manquant pour un fichier non-vide: {pkl_path}")
                    return self._create_empty_qtable()

                with open(hash_path, 'r') as f:
                    stored_hash = f.read().strip()
                    current_hash = self._calculate_hash(qtable)

                    # print(f"stored_hash = {stored_hash}, current_hash = {current_hash} for pkl_file = {pkl_path} and secret = {self.secret}")

                    if stored_hash != current_hash:
                        # logging.warning(f"Hash incorrect pour: {pkl_path}")
                        return self._create_empty_qtable()

                # logging.info(f"Q-table chargée avec succès: {pkl_path}")
                return qtable

            except Exception as e:
                logging.error(f"Erreur lors du chargement: {e}")
                return self._create_empty_qtable()

    async def save(self, qtable, name, side="right"):
        with self.lock:
            pkl_path, hash_path = self._get_file_paths(name, side)
            temp_pkl = pkl_path.with_suffix('.tmp')
            temp_hash = hash_path.with_suffix('.tmp')

            try:
                # Sauvegarder les données
                with open(temp_pkl, 'wb') as f:
                    pickle.dump(qtable, f)

                # Créer/mettre à jour le hash sécurisé
                hash_value = self._calculate_hash(qtable)
                with open(temp_hash, 'w') as f:
                    f.write(hash_value)

                # Renommer de manière atomique
                temp_pkl.rename(pkl_path)
                temp_hash.rename(hash_path)

                # logging.info(f"Q-table et hash sauvegardés: {pkl_path}")
                return True

            except Exception as e:
                logging.error(f"Erreur lors de la sauvegarde: {e}")
                # Nettoyage
                for temp_file in [temp_pkl, temp_hash]:
                    if temp_file.exists():
                        temp_file.unlink()
                return False
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



        
