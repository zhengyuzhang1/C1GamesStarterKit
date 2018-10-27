import gamelib
import random
import math
import warnings
import json
from sys import maxsize
from gamelib.game_state import is_stationary


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

Additional functions are made available by importing the AdvancedGameState 
class from gamelib/advanced.py as a replcement for the regular GameState class 
in game.py.

You can analyze action frames by modifying algocore.py.

The GameState.map object can be manually manipulated to create hypothetical 
board states. Though, we recommended making a copy of the map to preserve 
the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        random.seed()

        self.EMP_COUNT = 2
        self.ARENA_SIZE = 28
        self.HALF_ARENA = int(self.ARENA_SIZE / 2)
        self.breach_x = -1
        self.breach_y = -1
        self.UNIT_TYPE = -1
        self.ENEMY_HEALTH_CONSTANT_COUNT = 0
        self.EMP_COUNT = 1
        self.info_from_p2 = {}
        self.enemy_removed_units = []
        self.enemy_removed_units_dict = {}
        self.game_state = None
        self.actions = [[],[]]
        self.stationary_units = [{}, {}]
        self.flag_final_attack = False
        
        #strategy flags
        self.locs_block_and_final_attack = []
        

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        
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

        self.set_helper_map(config)
        
    def set_helper_map(self, config):
        self.helper_map = gamelib.GameMap(config)
        #if firewall is required for block, and so should not be removed in any case
        self.helper_map.attack_turn = [[{} for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
        self.helper_map.damage_turn = [[{} for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
        self.helper_map.remove_turn = [[[] for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
        self.helper_map.breach_turn = [[[] for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
        self.helper_map.n_units_ever_spawned = [[[0] * 7 for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
        self.helper_map.priority = [[0 for _ in range(self.ARENA_SIZE)] for _ in range(self.ARENA_SIZE)]
         
    def rank_locations_priority(self, location_list):
        return sorted(location_list, key = lambda x: self.helper_map.priority[x[0]][x[1]], reverse = True)
                
    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
                
        #if not first turn, parse last turn's action phase strings
        if self.game_state is not None:
            self.parse_action_phase()          
        
        self.__action_strings = []
        
        self.game_state = gamelib.AdvancedGameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(self.game_state.turn_number))
        #self.game_state.suppress_warnings(True)  # Uncomment this line to suppress warnings.        

        self.starter_algo(self.game_state)        
        
        self.game_state.submit_turn()
        
    def on_action_frame(self, action_string):
        self.__action_strings.append(action_string)
        
    def parse_action_phase(self):
        """
        This function is called every turn in game state wrapper as an argument.
        It records game_state from previous rounds. The first part records 
        breach_info, i.e., location damaged by enemy's information unit.
        The second part records firewalls removed by enemy. Third part
        records FILTERS built by enemy. Fourth part records DESTRUCTORS
        built by enemy.
        """
        #add actions of opponent
        self.actions[1].append(gamelib.Action(self.config, self.game_state, self.helper_map, self.__action_strings, 1))
        #add actions of self
        #self.actions[0].append(gamelib.Action(self.config, self.pre_game_state, self.helper_map, self.__action_strings, 0))                


    def is_firewall_horizontal(self, threshold_ratio):
        """
        Check if the possible positions for destructors and filters are as follows.
        If more than 20% of the expected position for filters and destructors are 
        in the actual positions, enemy is suspected to be building a horizontal firewall.
        """
        enemy_possible_destructors_pos = [[0, 14], [27, 14], [6, 16], [7, 16], [11, 16], [12, 16], [15, 16], [16, 16], [19, 16], [20, 16]]

        enemy_possible_filters_pos = [[1, 14], [2, 14], [25, 14], [26, 14], [3, 15], [24, 15], [4, 16], [5, 16], [6, 16], [7, 16], [8, 16], 
                                      [9, 16], [10, 16], [11, 16], [12,16], [13, 16], [14, 16], [15, 16], [16, 16], [17, 16], [18, 16], [19, 16], 
                                      [20, 16], [21, 16], [22, 16], [23, 16]]                     
        

        # gamelib.debug_write('enemy FILTERS actual locations: {}'.format(enemy_actual_filters_pos))

        # gamelib.debug_write('enemy DESTRUCTOR actual locations: {}'.format(enemy_actual_destructors_pos))

        destructor_count = 0
        filter_count = 0
        
        for x, y in enemy_possible_destructors_pos:
            if self.helper_map.n_units_ever_spawned[x][y][UNIT_TYPE_TO_INDEX[DESTRUCTOR]] > 0:
                destructor_count += 1

        for x, y in enemy_possible_filters_pos:
            if self.helper_map.n_units_ever_spawned[x][y][UNIT_TYPE_TO_INDEX[FILTER]] > 0:
                filter_count += 1
        
        d_prediction_accuracy = destructor_count / len(enemy_possible_destructors_pos)
        f_prediction_accuracy = filter_count / len(enemy_possible_filters_pos)
        
        return d_prediction_accuracy > threshold_ratio[0] and f_prediction_accuracy > threshold_ratio[1]
                
    def double_check_horizontal_firewall(self, rows, threshold_firewall):
        """
        Check if any row from 14 to 18 on the enemy's side 
        contains more than 8 firewalls. 
        """
        for row in rows:
            count = 0
            for x in range(self.ARENA_SIZE):
                if any(self.helper_map.n_units_ever_spawned[x][row][:3]):
                    count += 1
                    if count > threshold_firewall:
                        return True
        return False

    def strengthen_around(self, firewall_type, location):
        for pos in self.helper_map.get_locations_in_range(location, 1.5): 
            gamelib.debug_write('neighbor is: [{0}, {1}]'.format(pos[0], pos[1]))   
            self.game_state.attempt_spawn(firewall_type, pos)
           
    def remove_unattacked_undamaged_firewall(self, threshold_terms, locations = None):
        if locations is None:
            locations = self.helper_map.get_self_arena()       
        for x, y in locations:
            #current life of firewall on location:
            last_attack_turn = max(self.helper_map.attack_turn[x][y].keys())
            last_damage_turn = max(self.helper_map.damage_turn[x][y].keys())
            if self.game_state.turn_number - last_attack_turn > threshold_terms and self.game_state.turn_number - last_damage_turn > threshold_terms:
                self.game_state.attempt_remove((x,y))
        
    def block_and_final_attack(self, locs, scrambler_number, ping_number):
        l = []
        for loc in locs:
            neighbor = self.helper_map.get_locations_in_range(loc, 1.5) 
            l += [x for x in neighbor if x not in locs]
        locs += l
        
        wall_locs = list(map(lambda x: (x, x-12), range(13, 26)))
        attack_path = list(map(lambda x: (x, x-13), range(13, 27)))
        ping_loc = [[13, 0]]
        scrambler_loc = [[24, 10]]       
        
        weak_corner = self.get_weak_corner()
        if weak_corner == "left":
            for loc1 in [wall_locs, attack_path, ping_loc, scrambler_loc]:
                loc1 = self.helper_map.get_symmetry(loc1)

        filter_locs = locs + wall_locs
        self.game_state.restore_should()
        self.game_state.set_should(filter_locs)
        
        self.game_state.attempt_spawn(FILTER, filter_locs)
        ping_loc = [13, 0]
        scrambler_loc = [24, 10]
        
        if self.flag_final_attack:
            self.game_state.attempt_spawn(PING, ping_loc, ping_number)
            self.game_state.attempt_spawn(SCRAMBLER, scrambler_loc, scrambler_number)
            self.flag_final_attack = False
            self.game_state.restore_should()
            self.game_state.restore_shouldnot()
        
        if self.game_state.project_future_bits() >= scrambler_number + ping_number and all(map(lambda x:self.game_state.contains_stationary_unit(x) or (FILTER, int(x[0]), int(x[1])) in self.game_state._build_stack, wall_locs)):
            self.clear_path(attack_path)
            self.flag_final_attack = True                  
    
    def clear_path(self, locations):
        self.game_state.set_should(locations, False)
        self.game_state.attempt_remove(locations)
        self.game_state.set_shouldnot(locations)
        
    def get_weak_corner(self):
        n_attackers = [len(self.game_state.get_attackers(corner)) for corner in [[0, 14], [27, 14]]]
        if n_attackers[0] < n_attackers[1]:
            return "left"
        else:
            return "right"
        
    def starter_algo(self, game_state):

        self.locs_block_and_final_attack = self.game_state.locs_block_enemy_openings()
        if 0 < len(self.locs_block_and_final_attack) < 6:
            gamelib.debug_write("openings:{}".format(self.locs_block_and_final_attack))
            self.block_and_final_attack(self.locs_block_and_final_attack, 3, 33)
            return      
        
        #self.initial_firewall_setup(game_state)
        '''
        l0_l1_filters_positions = [[27, 13], [26, 12]]

        l3_filters_postions = [[ 6, 11],[ 7, 11],[ 9, 11],[ 10, 11],[ 11, 11],[ 13, 11],[ 14, 11],[15, 11],[ 16, 11],[ 17, 11],[ 18, 11],[19, 11],[ 20, 11],[ 21, 11],[ 22, 11],[23,11],[ 24, 11],[ 25, 11]]

        l4_l5_filters_positions = [[ 3, 10],[ 4, 9],[ 5, 9],[ 6, 9],[ 7, 9],[ 8, 9]]

        l2_destructors_positions = [[ 2 ,12]]

        l1_filters_positions = [[ 1, 13],[ 2, 13],[ 3, 13],[ 4, 13],[ 5, 13],[ 6, 13],[ 7, 13],[ 8, 13],[ 9, 13],[ 10, 13],[ 11, 13],[ 12, 13],[ 13, 13],[ 14, 13],[ 15, 13],[ 16, 13],[ 17, 13],[ 18, 13],[ 19, 13],[ 20, 13],[ 21, 13],[ 22, 13],[ 23, 13],[ 24, 13]]

        # l5_filters_positions = [[ 9, 9],[ 10, 9],[ 11, 9],[ 12, 9],[ 13, 9],[ 14, 9],[ 15, 9],[ 16, 9],[ 17, 9],[ 18, 9],[ 19, 9],[ 20, 9],[ 21, 9],[ 22, 9],[ 23, 9]]

        for position in l0_l1_filters_positions:
            self.restore_firewall(game_state, FILTER, position)

        for position in l3_filters_postions:
            self.restore_firewall(game_state, FILTER, position)

        for position in l4_l5_filters_positions:
            self.restore_firewall(game_state, FILTER, position)

        for position in l2_destructors_positions:
            self.restore_firewall(game_state, DESTRUCTOR, position)

        for position in l1_filters_positions:
            self.restore_firewall(game_state, FILTER, position)
        '''
        destructor_list_0 = [ [0, 13], [26, 13], [3, 11], [7, 11], [11, 11], [16, 11], [20, 11], [23, 11]]
        filter_list_0 = [[27, 13]]

        destructor_list_1 = [[13, 11], [2, 12], [25, 13]]
        filter_list_1 = [[1, 13], [3, 12], [2, 11], [5,11], [6, 11], [8, 11], [9, 11], [10,11], [12,11], [14,11], [15,11], [17,11], [18,11], [19,11], [21,11], [22,11], [24,11], [25,11], [26, 12]]

        filter_list_2 = [ [2, 13], [3, 13], [4, 13], [5, 13], [6, 13], [7, 13], [8, 13], [9, 13], [10, 13], [11, 13], [12, 13], [13,13], [14,13], [15, 13], [16, 13], [17, 13], [18, 13], [19, 13], [20, 13], [21, 13], [22, 13], [23, 13] ]
        destructor_list_2 = [ [1, 12], [2, 11] ]

        filter_list_3 = [[3, 10], [4, 9], [5, 9], [6, 9], [7, 9], [8, 9], [9, 9]]


        
        for location in self.rank_locations_priority(destructor_list_0):
            self.game_state.attempt_spawn(DESTRUCTOR, location, num=1)

        for location in self.rank_locations_priority(filter_list_0):
            self.game_state.attempt_spawn(FILTER, location, num=1)

        for location in self.rank_locations_priority(destructor_list_1):
            self.game_state.attempt_spawn(DESTRUCTOR, location, num=1)

        for location in self.rank_locations_priority(filter_list_1):
            self.game_state.attempt_spawn(FILTER, location, num=1)

        for location in self.rank_locations_priority(destructor_list_2):
            self.game_state.attempt_spawn(DESTRUCTOR, location, num=1)

        for location in self.rank_locations_priority(filter_list_2):
            self.game_state.attempt_spawn(FILTER, location, num=1)

        for location in self.rank_locations_priority(filter_list_3):
            self.game_state.attempt_spawn(FILTER, location, num=1)

        for location in [[22, 9], [5, 8], [23, 9]]:
            self.game_state.attempt_spawn(ENCRYPTOR, location, num=1)

 

  
        self.deploy_attackers(game_state)
        

    def restore_firewall(self, game_state, firewall, position):
        if game_state.can_spawn(firewall, position):
            game_state.attempt_spawn(firewall, position)

    def deploy_attackers(self, game_state):
        EMP_position = [24, 10] # Try [5, 8]?
        
        #if game_state.can_spawn(EMP, EMP_position, 1) and game_state.turn_number % 2 == 0:


        if game_state.turn_number ==0:
            while game_state.can_spawn(PING, [16, 2], 1):
                game_state.attempt_spawn(PING, [16, 2], 1)
        else:
            while game_state.can_spawn(EMP, EMP_position, 1):
                game_state.attempt_spawn(EMP, EMP_position, 1)




    def initial_firewall_setup(self, game_state):
        # round 0 DESTRUCTORs' positons
        round_zero_destructors_positons = [[ 3, 11],[ 5, 11],[ 8, 11],[ 12, 11],[ 14, 11],[ 17, 11],[ 20, 11],[ 24, 11]]

        # round 0 FILTERs' positions
        round_zero_filters_positons = [[ 0, 13],[ 1, 12],[ 26, 12],[ 2, 11]]

        for position in round_zero_destructors_positons:
            self.restore_firewall(game_state, DESTRUCTOR, position)

        for position in round_zero_filters_positons:
            self.restore_firewall(game_state, FILTER, position)

        

    # Detect opponent's removal behavior
    # If the removed unit has high stability, 
    # this usually means they are preparing to attack from that opening.

    # p1Units: [filters, encryptors, Destructors, ping?, EMP?, Scrambler? Remove?]
    # sublists of p1Units: [x, y, stability, id]
    

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
