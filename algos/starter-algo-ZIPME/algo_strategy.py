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
        self.HALF_MAP = 14
        self.breach_x = -1
        self.breach_y = -1
        self.UNIT_TYPE = -1
        self.ENEMY_HEALTH_CONSTANT_COUNT = 0
        self.EMP_COUNT = 1
        self.dic = {}
        self.info_from_p2 = {}
        self.enemy_removed_units = []
        self.enemy_removed_units_dict = {}

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        # game_state.suppress_warnings(True)  # Uncomment this line to suppress warnings.        

        self.enemyPrevHealth = game_state.enemy_health

        self.starter-algo(game_state)        

        self.enemyCurrHealth = game_state.enemy_health
        
        game_state.submit_turn()

    def parse_action_phase(self, turn_state):
        """
        This function is called every turn in game state wrapper as an argument.
        It records game_state from previous rounds. The first part records 
        breach_info, i.e., location damaged by enemy's information unit.
        The second part records firewalls removed by enemy.
        """
        game_state = gamelib.GameState(self.config, turn_state)

        # First part
        if len(game_state.breach_info) > 0 and game_state.breach_info[0][0][1] < self.HALF_MAP:
            self.breach_x = game_state.breach_info[0][0][0]
            self.breach_y = game_state.breach_info[0][0][1]            
            self.UNIT_TYPE = game_state.breach_info[0][2]
            gamelib.debug_write('Location [{0}, {1}] is under attack!'.format(self.breach_x, self.breach_y))    
        else:
            self.breach_x = -1
            self.breach_y = -1

        # Second part
        if len(game_state.p2_info[6]) > 0:
            if self.enemy_removed_units != game_state.p2_info[6]:
                self.enemy_removed_units = game_state.p2_info[6]
                gamelib.debug_write('Firewalls removed are: {}'.format(self.enemy_removed_units))
        else:
            self.info_from_p2 = []

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

        # if self.enemy_removed_units_dict[temp] >= 3:
            # gamelib.debug_write('Enemy has removed {0} for {1} times'.format(self.enemy_removed_units_dict[temp], self.enemy_removed_units_dict[temp]))

        for key, value in self.enemy_removed_units_dict.items():
            if value >= 3:
                gamelib.debug_write('Enemy has removed {0} for {1} times'.format(key, value))

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
            unit = game_state.game_map[location[0], location[1]][0]:
            if unit.stability == unit.max_stability:
                unit.last_attack_round += 1
            else
                unit.last_attack_round = 0
            if unit.last_attack_round == N_terms:
                game_state.attempt_remove(location)


    def starter-algo(self, game_state):

        destructors_positions_l1 = [[ 0, 13],[ 1, 12],[ 2, 11],[ 3, 10]]

        destructors_positions_l2 = [[ 1, 13],[ 2, 12],[ 3, 11],[ 4, 10]]

        for position in destructors_positions_l1:
            self.restoreFirewall(game_state, DESTRUCTOR, position)

        for position in destructors_positions_l2:
            self.restoreFirewall(game_state, DESTRUCTOR, position)

        self.check_firewall_pattern(game_state)

        # get EMP's position
        EMP_position = [ 14, 0]

        # get ping's position
        pings_position = [ 14, 0]

        while (game_state.number_affordable(EMP) > 0):
            # if EMP damanges opponent, summon ping
            if game_state.turn_number and self.enemyCurrHealth != self.enemyPrevHealth:
                if game_state.can_spawn(PING, pings_position, game_state.number_affordable(PING)):
                    game_state.attempt_spawn(PING, pings_position, game_state.number_affordable(PING))

            if game_state.can_spawn(EMP, EMP_position, game_state.number_affordable(EMP)):
                game_state.attempt_spawn(EMP, EMP_position, game_state.number_affordable(EMP))        

    def starter-algo_initialSetup(self, game_state):

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
