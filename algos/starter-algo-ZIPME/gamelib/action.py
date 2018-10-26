from .util import debug_write
from .unit_group import UnitGroup
import json

from .game_state import is_stationary

class Action:
    """Represents actions of a players in a turn
    Provides methods related to resources and unit deployment

    Attributes:
        * UNIT_TYPE_TO_INDEX (dict): Maps a unit to a corresponding index
        * FILTER (str): A constant representing the filter unit
        * ENCRYPTOR (str): A constant representing the encryptor unit
        * DESTRUCTOR (str): A constant representing the destructor unit
        * PING (str): A constant representing the ping unit
        * EMP (str): A constant representing the emp unit
        * SCRAMBLER (str): A constant representing the scrambler unit
        * FIREWALL_TYPES (list): A list of the firewall units

        * ARENA_SIZE (int): The size of the arena
        * HALF_ARENA (int): Half the size of the arena
        * BITS (int): A constant representing the bits resource
        * CORES (int): A constant representing the cores resource
         
        * game_map (:obj: GameMap): The current GameMap. To retrieve a list of GameUnits at a location, use game_map[x, y]
        * turn_number (int): The current turn number. Starts at 0.
        * my_health (int): Your current remaining health
        * my_time (int): The time you took to submit your previous turn
        * enemy_health (int): Your opponents current remaining health
        * enemy_time (int): Your opponents current remaining time

    """

    def __init__(self, config, game_state, helper_map, serialized_strings, player_index):
        """ Setup a turns variables using arguments passed

        Args:
            * config (JSON): A json object containing information about the game
            * serialized_string (string): A string containing information about the game state at the start of this turn

        """
    
        self.player_index = player_index
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, REMOVE, FIREWALL_TYPES, INFORMATION_TYPES, ALL_UNITS, UNIT_TYPE_TO_INDEX
        UNIT_TYPE_TO_INDEX = {}
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        REMOVE = config["unitInformation"][6]["shorthand"]
        UNIT_TYPE_TO_INDEX[FILTER] = 0
        UNIT_TYPE_TO_INDEX[ENCRYPTOR] = 1
        UNIT_TYPE_TO_INDEX[DESTRUCTOR] = 2
        UNIT_TYPE_TO_INDEX[PING] = 3
        UNIT_TYPE_TO_INDEX[EMP] = 4
        UNIT_TYPE_TO_INDEX[SCRAMBLER] = 5
        UNIT_TYPE_TO_INDEX[REMOVE] = 6
        ALL_UNITS = [FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, REMOVE]
        FIREWALL_TYPES = [FILTER, ENCRYPTOR, DESTRUCTOR]
        INFORMATION_TYPES = [PING, EMP, SCRAMBLER]
        
        global SELFDESTRUCT, BREACH, DAMAGE, SHIELD, MOVE, SPAWN, DEATH, ATTACK, EVENT, ALL_EVENTS
        EVENT = "events"
        SELFDESTRUCT = "selfDestruct"
        BREACH = "breach"
        DAMAGE = "damage"
        SHIELD = "shield"
        MOVE = "move"
        SPAWN = "spawn"
        DEATH = "death"
        ATTACK = "attack"
        ALL_EVENTS = [SELFDESTRUCT, BREACH, DAMAGE, SHIELD, MOVE, SPAWN, DEATH, ATTACK]
        
        self.ARENA_SIZE = 28
        self.HALF_ARENA = int(self.ARENA_SIZE / 2)
        self.BITS = 0
        self.CORES = 1

        self.__parse_frames(game_state, helper_map, serialized_strings, player_index)

    def single_player_event(self, event, player_id):
        return filter(lambda x: x[-1] == player_id, event)
    
    def __parse_frames(self, game_state, helper_map, serialized_strings, player_index):
        """
        Fills in map based on the serialized game state so that self.game_map[x,y] is a list of GameUnits at that location.
        state_line is the game state as a json string.
        """
        
        self.n_frames = len(serialized_strings)
        spawn_frame = json.loads(serialized_strings[0])
        self.turn_number = spawn_frame["turnInfo"][1]
        if player_index == 0:
            STATS = "p1Stats"
            UNITS = "p1Units"
            PLAYER_ID = "1"
        else:
            STATS = "p2Stats"
            UNITS = "p2Units"
            PLAYER_ID = "2" 
        self.health, cores, bits, time = map(float, spawn_frame[STATS])
        units = spawn_frame[UNITS]
        self.cores_used = cores - game_state._player_resources[player_index]["cores"]
        self.bits_used = bits - game_state._player_resources[player_index]["bits"]
        
        #parse spawned units
        self.firewall_spawned = [[], [], []]
        self.removed = [[], [], []]
        self.attacker_group_spawned = [[], [], []]
        information_units_spawned = [{}, {}, {}]
        self.unit_id_to_unit_group = {}
        for unit in self.single_player_event(spawn_frame[EVENT][SPAWN], PLAYER_ID):
            loc, unit_type_id, unit_id, play_id = unit
            x, y = map(int, loc)
            unit_type = ALL_UNITS[int(unit_type_id)]
            helper_map.n_units_ever_spawned[x][y][int(unit_type_id)] += 1
            if is_stationary(unit_type):
                self.firewall_spawned[unit_type_id].append((x,y))
            elif unit_type == REMOVE:
                helper_map.remove_turns[x][y].append(self.turn_number)
                for i in range(3):
                    for u2 in units[i]:
                        if [u2[0], u2[1]] == loc:
                            self.removed[i].append((x,y,float(u2[2])))
            else:
                if (x,y) not in information_units_spawned[int(unit_type_id)-3]:
                    information_units_spawned[int(unit_type_id)-3][(x,y)] = [unit_id]
                else:
                    information_units_spawned[int(unit_type_id)-3][(x,y)].append(unit_id)
        for i in range(3):
            for key, val in information_units_spawned[i]:
                unit_group = UnitGroup(INFORMATION_TYPES[i], [key], len(val))
                self.attacker_group_spawned[i].append(unit_group)
                self.unit_id_to_unit_group.update(dict.fromkeys(val, unit_group))
        
        #parse information unit_group path and damage dealt
        for frame in map(json.loads, serialized_strings):
            for attacker, receiver, damage, attacker_type_id, attacker_id, receiver_id, player_id in self.single_player_event(frame[EVENT][ATTACK], PLAYER_ID):
                x, y = map(int, attacker)
                x2, y2 = map(int, receiver)
                helper_map.attack_turn[x][y].append(self.turn_number)
                helper_map.damage_turn[x2][y2].append(self.turn_number)
                if attacker_type_id in ["3", "4", "5"]:
                    unit_group = self.unit_id_to_unit_group[attacker_id]
                    unit_group.add_attack(float(damage))
            for pre_loc, loc, not_used, unit_type_id, unit_id, player_index in self.single_player_event(frame[EVENT][MOVE], PLAYER_ID):
                unit_group = self.unit_id_to_unit_group[unit_id]
                x, y = map(int, loc)
                unit_group.append_path((x,y))
            for loc, damage, unit_type_id, unit_id, player_index in self.single_player_event(frame[EVENT][BREACH], PLAYER_ID):
                unit_group = self.unit_id_to_unit_group[unit_id]
                unit_group.add_breach(1)
                x, y = map(int, loc)
                helper_map.breach_turn[x][y].append(self.turn_number)
            for loc, receivers, damage, unit_type_id, unit_id, player_index in self.single_player_event(frame[EVENT][SELFDESTRUCT], PLAYER_ID):
                unit_group = self.unit_id_to_unit_group[unit_id]
                unit_group.add_selfdestruct_damage(damage * len(receivers))
                
                
        
                
                        
                
                
                
  



 
    