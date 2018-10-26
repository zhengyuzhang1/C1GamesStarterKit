import gamelib
import random
import math
import warnings
import json
from sys import maxsize

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
        self.dic = {}
        self.info_from_p2 = {}
        self.enemy_removed_units = []
        self.enemy_removed_units_dict = {}
        self.pre_game_state = None
        self.actions = [[],[]]
        

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        self.set_helper_map(config)
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]

    def set_helper_map(self, config):
        self.helper_map = gamelib.GameMap(config)
        #if firewall is required for block, and so should not be removed in any case
        self.helper_map.necessity = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        self.helper_map.turn_last_attack = [[-1] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        self.helper_map.turn_last_damage = [[-1] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        
    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
                
        self.game_state = gamelib.GameState(self.config, turn_state)
        #if not first turn, parse last turn's action phase strings and update states difference
        if self.pre_game_state is not None:
            self.parse_action_phase()
            self.set_turn_change()
            
        self.pre_game_state = self.game_state
        self.__action_strings = []
        
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(self.game_state.turn_number))
        # game_state.suppress_warnings(True)  # Uncomment this line to suppress warnings.        

        self.starter_algo(self.game_state)        
        
        self.game_state.submit_turn()

    def set_turn_change(self):
        self.enemyPrevHealth = self.game_state.enemy_health
        self.enemyCurrHealth = self.game_state.enemy_health
        
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
        self.actions[1].append(gamelib.Action(self.config, self.pre_game_state, self.helper_map, self.__action_strings, 1))
        #add actions of self
        #self.actions[0].append(gamelib.Action(self.config, self.pre_game_state, self.helper_map, self.__action_strings, 0))                

    def get_unit_type(self, unit_type):
        if unit_type == 3:
            return "PING"
        elif unit_type == 4:
            return "EMP"
        elif unit_type == 5:
            return "SCRAMBLER"
        else:
            return "ERROR"

    def get_location(self, p2_info_units_info):
        """
        Returns locations after parsing p2_info
        [[19, 16, 60.0, '18'], [18, 16, 60.0, '20']

        """
        actual_locations = []
        for each_info_unit in p2_info_units_info:
            actual_locations.append([each_info_unit[0], each_info_unit[1]])

        return actual_locations

    def check_firewall_pattern(self, game_state):
        """
        This function is called in the main(). It detects the
        firewalls removed by enemy every turn
        """
        for each_firewall in self.enemy_removed_units:
            self.check_firewall_pattern_helper(game_state, each_firewall[1], each_firewall[0])

    def check_firewall_pattern_helper(self, game_state, row, col):
        temp = ()
        temp = temp + (col,)
        temp = temp + (row,)
        
        if temp in self.enemy_removed_units_dict.keys():
            self.enemy_removed_units_dict[temp] += 1
        else:
            self.enemy_removed_units_dict[temp] = 1

        for key, value in self.enemy_removed_units_dict.items():
            if value >= 3:
                # TO DO
                gamelib.debug_write('Enemy has removed {0} for {1} times'.format(key, value))

    def is_firewall_horizontal(self, game_state):
        """
        Check if the possible positions for destructors and filters are as follows.
        If more than 20% of the expected position for filters and destructors are 
        in the actual positions, enemy is suspected to be building a horizontal firewall.
        """
        enemy_possible_destructors_pos = [[0, 14], [27, 14], [6, 16], [7, 16], [11, 16], [12, 16], [15, 16], [16, 16], [19, 16], [20, 16]]

        enemy_possible_filters_pos = [[1, 14], [2, 14], [25, 14], [26, 14], [3, 15], [24, 15], [4, 16], [5, 16], [6, 16], [7, 16], [8, 16], 
                                      [9, 16], [10, 16], [11, 16], [12,16], [13, 16], [14, 16], [15, 16], [16, 16], [17, 16], [18, 16], [19, 16], 
                                      [20, 16], [21, 16], [22, 16], [23, 16]]                     
         
        enemy_actual_filters_pos = self.get_location(self.enemy_filters_units)        
        # gamelib.debug_write('enemy FILTERS actual locations: {}'.format(enemy_actual_filters_pos))

        enemy_actual_destructors_pos = self.get_location(self.enemy_destructors_units)
        # gamelib.debug_write('enemy DESTRUCTOR actual locations: {}'.format(enemy_actual_destructors_pos))

        destructor_count = 0
        filter_count = 0
        
        for each_possible_d_pos in enemy_possible_destructors_pos:
            for each_actual_d_pos in enemy_actual_destructors_pos:                
                if self.actual_expected_same_location(each_possible_d_pos[0], each_possible_d_pos[1], each_actual_d_pos[0], each_actual_d_pos[1]):
                    destructor_count += 1

        for each_possible_f_pos in enemy_possible_filters_pos:
            for each_actual_f_pos in enemy_actual_filters_pos:
                if self.actual_expected_same_location(each_possible_f_pos[0], each_possible_f_pos[1], each_actual_f_pos[0], each_actual_f_pos[1]):
                    filter_count += 1
        
        d_prediction_accuracy = destructor_count / len(enemy_possible_destructors_pos)
        f_prediction_accuracy = filter_count / len(enemy_possible_filters_pos)
        
        return d_prediction_accuracy > 0.2 and f_prediction_accuracy > 0.2
                
    def double_check_horizontal_firewall(self, game_state):
        """
        Check if any row from 14 to 18 on the enemy's side 
        contains more than 8 firewalls. 
        """
        enemy_actual_filters_pos = self.get_location(self.enemy_filters_units)        
        # gamelib.debug_write('enemy FILTERS actual locations: {}'.format(enemy_actual_filters_pos))

        enemy_actual_destructors_pos = self.get_location(self.enemy_destructors_units)
        # gamelib.debug_write('enemy DESTRUCTOR actual locations: {}'.format(enemy_actual_destructors_pos))

        row_dict = {}

        for each_actual_f_pos in enemy_actual_filters_pos:
            if each_actual_f_pos[1] in row_dict:
                row_dict[each_actual_f_pos[1]] += 1
            else:
                row_dict[each_actual_f_pos[1]] = 1

        for each_actual_d_pos in enemy_actual_destructors_pos:
            if each_actual_d_pos[1] in row_dict:
                row_dict[each_actual_d_pos[1]] += 1
            else:
                row_dict[each_actual_d_pos[1]] = 1

        gamelib.debug_write('row_dict: {}'.format(row_dict))

        for key, value in row_dict.items():
            if value >= 8 and key <= 18 and key >= 14:                
                gamelib.debug_write('More than 8 locations in ROW {} are filled!'.format(key))
                return True

    def actual_expected_same_location(self, actual_row, actual_col, expected_row, expected_col):
        """
        Check if actual location is same as expected location.
        """
        if actual_row == expected_row and actual_col == expected_col:
            return True
        else:
            return False

    def record_damage(self, game_state, row, col):
        if row == -1 or col == -1:
            return
            
        temp = ()
        temp = temp + (col,)
        temp = temp + (row,)
        
        if temp in self.dic.keys():
            self.dic[temp] += 1
        else:
            self.dic[temp] = 1

        if self.dic[temp] >= 3:
            gamelib.debug_write('Printing dic...\n {}'.format(self.dic))
            self.time_for_action(game_state, row, col)

    def time_for_action(self, game_state, row, col):
        for pos in self.damaged_neighbors(game_state, row, col): 
            gamelib.debug_write('neighbor is: [{0}, {1}]'.format(pos[0], pos[1]))   
            self.restoreFirewall(game_state, DESTRUCTOR, pos)

    def damaged_neighbors(self, game_state, row, col):
        """
        Return positions around the location that is damaged by enemy.
        """
        o_clock_9 = []        
        o_clock_9.append(col + 1)
        o_clock_9.append(row - 1)

        o_clock_3 = []        
        o_clock_3.append(col - 1)
        o_clock_3.append(row + 1)
        
        o_clock_1 = []        
        o_clock_1.append(col + 1)
        o_clock_1.append(row)

        o_clock_10 = []        
        o_clock_10.append(col)
        o_clock_10.append(row + 1)

        return o_clock_9, o_clock_3, o_clock_1, o_clock_10

    def record_damage(self, game_state, row, col):
        """
        Record the location damaged by enemy. If a location
        is attacked by more than 3 times, we spawn firewalls
        around its neighbors.
        """
        if row == -1 or col == -1:
            return
            
        temp = ()
        temp = temp + (col,)
        temp = temp + (row,)
        
        if temp in self.dic.keys():
            self.dic[temp] += 1
        else:
            self.dic[temp] = 1

        if self.dic[temp] >= 3:
            gamelib.debug_write('Printing dic...\n {}'.format(self.dic))
            self.time_for_action(game_state, row, col)

    def time_for_action(self, game_state, row, col):
        for pos in self.damaged_neighbors(game_state, row, col): 
            gamelib.debug_write('neighbor is: [{0}, {1}]'.format(pos[0], pos[1]))   
            self.restoreFirewall(game_state, DESTRUCTOR, pos)

    def restoreFirewall(self, game_state, firewall, position):
        if game_state.can_spawn(firewall, position):
            game_state.attempt_spawn(firewall, position)

    def remove_unattacked_firewall(self, game_state, N_terms, locations):
        for location in locations:
            if location[1] >= game_state.HALF_ARENA:
                warnings.warn("Could not remove a unit from {}. Location is enemy territory.".format(location))
                continue
            if not game_state.contains_stationary_unit(location):
                warnings.warn("Could not remove a unit from {}. Location has no firewall.".format(location))
                continue
                #current life of firewall on location:
            unit = game_state.game_map[location[0], location[1]][0]
            if unit.stability == unit.max_stability:
                unit.last_attack_round += 1
            else:
                unit.last_attack_round = 0
            if unit.last_attack_round == N_terms:
                game_state.attempt_remove(location)

    def starter_algo(self, game_state):

        destructors_positions_l1 = [[ 0, 13]]

        destructors_positions_l2 = []
        """
        for player in [0,1]:
            gamelib.debug_write('Defense line for player {} is:\n'.format(player), game_state.get_front_defense_line(0))
            gamelib.debug_write('Opening for player {} is:\n'.format(player), game_state.get_openings(0))
        """
        for position in destructors_positions_l1:
            self.restoreFirewall(game_state, DESTRUCTOR, position)

        for position in destructors_positions_l2:
            self.restoreFirewall(game_state, DESTRUCTOR, position)

        self.check_firewall_pattern(game_state)

        if game_state.turn_number == 1 and self.is_firewall_horizontal(game_state):
            gamelib.debug_write('\t* * * ALERT * * * \nEnemy\'s firewall is horizontal!')

        if game_state.turn_number > 1 and self.double_check_horizontal_firewall(game_state):
            gamelib.debug_write('\t* * * ALERT * * * \nEnemy\'s firewall is horizontal!')            


        # get EMP's position
        EMP_position = [ 13, 0]

        # get ping's position
        pings_position = [ 27, 13]

        while (game_state.number_affordable(EMP) > 0):
            # if EMP damanges opponent, summon ping
            if game_state.turn_number == 0:# and self.enemyCurrHealth != self.enemyPrevHealth:
                if game_state.can_spawn(PING, pings_position, game_state.number_affordable(PING)):
                    game_state.attempt_spawn(PING, pings_position, game_state.number_affordable(PING))

            if game_state.can_spawn(EMP, EMP_position, game_state.number_affordable(EMP)):
                game_state.attempt_spawn(EMP, EMP_position, game_state.number_affordable(EMP))        

        if game_state.contains_stationary_unit((0,13)):
            game_state.attempt_remove((0,13))
    
    def starter_algo_initialSetup(self, game_state):

        destructors_positions_l0 = [[ 7, 10], [ 21, 10], [14, 10], [0, 13], [27, 13]]

        filters_positions_l0 = []

        

    # Detect opponent's removal behavior
    # If the removed unit has high stability, 
    # this usually means they are preparing to attack from that opening.

    # p1Units: [filters, encryptors, Destructors, ping?, EMP?, Scrambler? Remove?]
    # sublists of p1Units: [x, y, stability, id]
    

if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
