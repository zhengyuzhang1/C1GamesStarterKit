import math
import json
import warnings
import queue

from .navigation import ShortestPathFinder
from .util import send_command, debug_write
from .unit import GameUnit
from .game_map import GameMap

def is_stationary(unit_type):
    return unit_type in FIREWALL_TYPES

class GameState:
    """Represents the entire gamestate for a given turn
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

    def __init__(self, config, serialized_string):
        """ Setup a turns variables using arguments passed

        Args:
            * config (JSON): A json object containing information about the game
            * serialized_string (string): A string containing information about the game state at the start of this turn

        """
        self.serialized_string = serialized_string
        self.config = config

        self.ARENA_SIZE = 28
        self.HALF_ARENA = int(self.ARENA_SIZE / 2)
        self.BITS = 0
        self.CORES = 1

        self.game_map = GameMap(self.config)
        self._shortest_path_finder = ShortestPathFinder()
        self._build_stack = []
        self._deploy_stack = []
        self._player_resources = [
                {'cores': 0, 'bits': 0},  # player 0, which is you
                {'cores': 0, 'bits': 0}]  # player 1, which is the opponent
        self.__parse_state(serialized_string)
        
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
        
        self.should = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        self.shouldnot = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
    
    def restore_should(self):
        self.should = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        
    def restore_shouldnot(self):
        self.shouldnot = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
    
    def set_should(self, locations = [], val):
        for x, y in locations:
            self.should[x][y] = val
    
    def set_shouldnot(self, locations = [], val):
        for x, y in locations:
            self.shouldnot[x][y] = val
        
    def __parse_state(self, state_line):
        """
        Fills in map based on the serialized game state so that self.game_map[x,y] is a list of GameUnits at that location.
        state_line is the game state as a json string.
        """
        state = json.loads(state_line)

        self.breach_info = state["events"]["breach"]
        self.p2_info = state["p2Units"]

        turn_info = state["turnInfo"]
        self.turn_number = int(turn_info[1])

        p1_health, p1_cores, p1_bits, p1_time = map(float, state["p1Stats"][:4])
        p2_health, p2_cores, p2_bits, p2_time = map(float, state["p2Stats"][:4])

        self.my_health = p1_health
        self.my_time = p1_time
        self.enemy_health = p2_health
        self.enemy_time = p2_time

        self._player_resources = [
            {'cores': p1_cores, 'bits': p1_bits},
            {'cores': p2_cores, 'bits': p2_bits}]

        p1units = state["p1Units"]
        p2units = state["p2Units"]

        self.__create_parsed_units(p1units, 0)
        self.__create_parsed_units(p2units, 1)

    def __create_parsed_units(self, units, player_number):
        """
        Helper function for __parse_state to add units to the map.
        """
        typedef = self.config.get("unitInformation")
        for i, unit_types in enumerate(units):
            for uinfo in unit_types:
                unit_type = typedef[i].get("shorthand")
                sx, sy, shp = uinfo[:3]
                x, y = map(int, [sx, sy])
                hp = float(shp)
                # This depends on RM always being the last type to be processed
                if unit_type == REMOVE:
                    try:
                        self.game_map[x,y][0].pending_removal = True
                    except:
                        print("Error! Program tried to die while parsing REMOVE unit")
                unit = GameUnit(unit_type, self.config, player_number, hp, x, y)
                self.game_map[x,y].append(unit)

    def __resource_required(self, unit_type):
        return self.CORES if is_stationary(unit_type) else self.BITS

    def __set_resource(self, resource_type, amount, player_index=0):
        """
        Sets the resources for the given player_index and resource_type.
        Is automatically called by other provided functions. 
        """
        if resource_type == self.BITS:
            resource_key = 'bits'
        elif resource_type == self.CORES:
            resource_key = 'cores'
        held_resource = self.get_resource(resource_type, player_index)
        self._player_resources[player_index][resource_key] = held_resource + amount

    def _invalid_player_index(self, index):
        warnings.warn("Invalid player index {} passed, player index should always be 0 (yourself) or 1 (your opponent)".format(index))
    
    def _invalid_unit(self, unit):
        warnings.warn("Invalid unit {}".format(unit))

    #added by zzy
    def get_defense_line(self, player_index = 1):
        dist = [[float('inf')] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        from_which = [[None] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        visited = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        start = (0, self.HALF_ARENA - 1 + player_index)
        end = (self.ARENA_SIZE - 1, self.HALF_ARENA - 1 + player_index)
        visited = [[False] * self.ARENA_SIZE for _ in range(self.ARENA_SIZE)]
        distance = 0
        if not self.contains_stationary_unit(start):
            distance += 1
        dist[start[0]][start[1]] = distance
        layer = [queue.Queue() for _ in range(self.ARENA_SIZE+1)]
        layer[distance].put(start)
        flag_done = False
        while not flag_done:
            while not layer[distance].empty():
                x, y = layer[distance].get()
                if visited[x][y]:
                    continue
                visited[x][y] = True
                if (x, y) == end:
                    flag_done = True
                    break
                for dx, dy in [(1,0),(1,1),(1,-1),(0,1),(0,-1),(-1,1),(-1,-1),(-1,0)]:
                    x2, y2 = x + dx, y + dy
                    if not self.game_map.in_arena_bounds((x2,y2)):
                        continue
                    if player_index == 1 and y2 < self.HALF_ARENA or player_index == 0 and y2 >= self.HALF_ARENA:
                        continue
                    if visited[x2][y2]:
                        continue
                    distance2 = distance
                    #gamelib.debug_write('{},{} distance:{}\n'.format(x2,y2,distance2))
                    if not self.contains_stationary_unit((x2,y2)):
                        distance2 += 1
                    if distance2 < dist[x2][y2]:
                        dist[x2][y2] = distance2
                        from_which[x2][y2] = x, y
                    layer[distance2].put((x2, y2))                   
            distance += 1
        line = []
        p = end
        line.append(p)
        while p != start:
            p = from_which[p[0]][p[1]]
            line.append(p)
        return line
            
    #added by zzy
    def get_openings(self, defense_line):
        return list(filter(lambda x: not self.contains_stationary_unit(x), defense_line))
    
    def can_block_enemy_openings(self, openings):
        return all(map(lambda loc: loc in self.game_map.get_row(self.HALF_ARENA), openings))
        
    def locs_block_enemy_openings(self):
        openings = list(filter(lambda x: not self.contains_stationary_unit(x), self.game_map.get_row(14)))
        return list(map(lambda x: (x[0], x[1]-1), openings))
    
    def opening_to_start(self, opening, target_edge):
        pass
        
    def submit_turn(self):
        """Submit and end your turn.
        Must be called at the end of your turn or the algo will hang.
        
        """
        build_string = json.dumps(self._build_stack)
        deploy_string = json.dumps(self._deploy_stack)
        send_command(build_string)
        send_command(deploy_string)

    def get_resource(self, resource_type, player_index = 0):
        """Gets a players resources

        Args:
            * resource_type: self.CORES or self.BITS
            * player_index: The index corresponding to the player whos resources you are querying, 0 for you 1 for the enemy

        Returns:
            The number of the given resource the given player controls

        """
        if not player_index == 1 and not player_index == 0:
            self._invalid_player_index(player_index)
        if not resource_type == self.BITS and not resource_type == self.CORES:
            warnings.warn("Invalid resource_type '{}'. Please use game_state.BITS or game_state.CORES".format(resource_type))

        if resource_type == self.BITS:
            resource_key = 'bits'
        elif resource_type == self.CORES:
            resource_key = 'cores'
        resources = self._player_resources[player_index]
        return resources.get(resource_key, None)

    def number_affordable(self, unit_type):
        """The number of units of a given type we can afford

        Args:
            * unit_type: A unit type, PING, FILTER, etc.

        Returns:
            The number of units affordable of the given unit_type.

        """
        if unit_type not in ALL_UNITS:
            self._invalid_unit(unit_type)
            return

        cost = self.type_cost(unit_type)
        resource_type = self.__resource_required(unit_type)
        player_held = self.get_resource(resource_type)
        return math.floor(player_held / cost)

    def project_future_bits(self, turns_in_future=1, player_index=0, current_bits=None):
        """Predicts the number of bits we will have on a future turn

        Args:
            * turns_in_future: The number of turns in the future we want to look forward to predict
            * player_index: The player whos bits we are tracking
            * current_bits: If we pass a value here, we will use that value instead of the current bits of the given player.

        Returns:
            The number of bits the given player will have after the given number of turns

        """

        if turns_in_future < 1 or turns_in_future > 99:
            warnings.warn("Invalid turns in future used ({}). Turns in future should be between 1 and 99".format(turns_in_future))
        if not player_index == 1 and not player_index == 0:
            self._invalid_player_index(player_index)
        if type(current_bits) == int and current_bits < 0:
            warnings.warn("Invalid current bits ({}). Current bits cannot be negative.".format(current_bits))

        bits = self.get_resource(self.BITS, player_index) if not current_bits else current_bits
        for increment in range(1, turns_in_future + 1):
            current_turn = self.turn_number + increment
            bits *= (1 - self.config["resources"]["bitDecayPerRound"])
            bits_gained = self.config["resources"]["bitsPerRound"] + (current_turn // self.config["resources"]["turnIntervalForBitSchedule"])
            bits += bits_gained
            bits = round(bits, 1)
        return bits

    def type_cost(self, unit_type):
        """Gets the cost of a unit based on its type

        Args:
            * unit_type: The units type

        Returns:
            The units cost

        """
        if unit_type not in ALL_UNITS:
            self._invalid_unit(unit_type)
            return

        unit_def = self.config["unitInformation"][UNIT_TYPE_TO_INDEX[unit_type]]
        return unit_def.get('cost')

    def can_spawn(self, unit_type, location, num=1):
        """Check if we can spawn a unit at a location. 

        To units, we need to be able to afford them, and the location must be
        in bounds, unblocked, on our side of the map, not on top of a unit we can't stack with, 
        and on an edge if the unit is information.

        Args:
            * unit_type: The type of the unit
            * location: The location we want to spawn the unit
            * num: The number of units we want to spawn

        Returns:
            True if we can spawn the unit(s)

        """
        if unit_type not in ALL_UNITS:
            self._invalid_unit(unit_type)
            return
        
        if not self.game_map.in_arena_bounds(location):
            return False

        affordable = self.number_affordable(unit_type) >= num
        stationary = is_stationary(unit_type)
        blocked = self.contains_stationary_unit(location) or (stationary and len(self.game_map[location[0],location[1]]) > 0)
        correct_territory = location[1] < self.HALF_ARENA
        on_edge = location in (self.game_map.get_edge_locations(self.game_map.BOTTOM_LEFT) + self.game_map.get_edge_locations(self.game_map.BOTTOM_RIGHT))
        should = not self.shouldnot[location[0]][location[1]]
        
        return (affordable and correct_territory and not blocked and
                (stationary or on_edge) and
                (not stationary or num == 1) and should)

    def attempt_spawn(self, unit_type, locations, num=1):
        """Attempts to spawn new units with the type given in the given locations.

        Args:
            * unit_type: The type of unit we want to spawn
            * locations: A single location or list of locations to spawn units at
            * num: The number of units of unit_type to deploy at the given location(s)

        Returns:
            The number of units successfully spawned

        """
        if unit_type not in ALL_UNITS:
            self._invalid_unit(unit_type)
            return
        if num < 1:
            warnings.warn("Attempted to spawn fewer than one units! ({})".format(num))
            return
      
        if type(locations[0]) == int:
            locations = [locations]
        spawned_units = 0
        for location in locations:
            for i in range(num):
                if self.can_spawn(unit_type, location):
                    x, y = map(int, location)
                    cost = self.type_cost(unit_type)
                    resource_type = self.__resource_required(unit_type)
                    self.__set_resource(resource_type, 0 - cost)
                    self.game_map.add_unit(unit_type, location, 0)
                    if is_stationary(unit_type):
                        self._build_stack.append((unit_type, x, y))
                    else:
                        self._deploy_stack.append((unit_type, x, y))
                    spawned_units += 1
                else:
                    warnings.warn("Could not spawn {} number {} at location {}. Location is blocked, invalid, or you don't have enough resources.".format(unit_type, i, location))
        return spawned_units

    def revoke_spawn(self, unit_type, locations, num=1):
        if unit_type not in ALL_UNITS:
            self._invalid_unit(unit_type)
            return
        if num < 1:
            return
      
        if type(locations[0]) == int:
            locations = [locations]
        revoked_units = 0
        for x, y in locations:
            item = (unit_type, x, y)
            for i in range(num):
                if is_stationary(unit_type) and item in self._build_stack:
                    self._build_stack.remove(item)
                elif not is_stationary(unit_type) and item in self._deploy_stack:
                    self._deploy_stack.remove(item)
                    revoked_units += 1
                else:
                    warnings.warn("Could not revoke {} number {} at location {}.".format(unit_type, i, (x,y)))
        return revoked_units
        
    def attempt_remove(self, locations):
        """Attempts to remove existing friendly firewalls in the given locations.

        Args:
            * locations: A location or list of locations we want to remove firewalls from

        Returns:
            The number of firewalls successfully flagged for removal

        """
        if type(locations[0]) == int:
            locations = [locations]
        removed_units = 0
        for location in locations:
            if location[1] < self.HALF_ARENA and self.contains_stationary_unit(location):
                x, y = map(int, location)
                if self.should[x][y]:
                    return
                self._build_stack.append((REMOVE, x, y))
                removed_units += 1
            else:
                warnings.warn("Could not remove a unit from {}. Location has no firewall or is enemy territory.".format(location))
        return removed_units
        
    def find_path_to_edge(self, start_location, target_edge):
        """Gets the path a unit at a given location would take

        Args:
            * start_location: The location of a hypothetical unit
            * target_edge: The edge the unit wants to reach. game_map.TOP_LEFT, game_map.BOTTOM_RIGHT, etc.

        Returns:
            A list of locations corresponding to the path the unit would take 
            to get from it's starting location to the best available end location

        """
        if self.contains_stationary_unit(start_location):
            warnings.warn("Attempted to perform pathing from blocked starting location {}".format(start_location))
            return
        end_points = self.game_map.get_edge_locations(target_edge)
        return self._shortest_path_finder.navigate_multiple_endpoints(start_location, end_points, self)

    def contains_stationary_unit(self, location):
        """Check if a location is blocked

        Args:
            * location: The location to check

        Returns:
            True if there is a stationary unit at the location, False otherwise
            
        """
        x, y = map(int, location)
        for unit in self.game_map[x,y]:
            if unit.stationary:
                return unit
        return False

    def suppress_warnings(self, suppress):
        """Suppress all warnings

        Args: 
            * suppress: If true, disable warnings. If false, enable warnings.
            
        """

        if suppress:
            warnings.filterwarnings("ignore")
        else:
            warnings.resetwarnings()

