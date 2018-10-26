#!/usr/bin/env python3
# -*- coding: utf-8 -*-
class UnitGroup:
    
    def __int__(self, unit_type, path, number = 1, attack = 0., breach = 0):
        self
        self.number = number
        self.unit_type = unit_type
        self.path = path
        self.attack = attack
        self.breach = breach
        
    def add_breach(self, n_breach = 1):
        self.breach += n_breach
    
    def append_path(self, nxt):
        self.path.append(nxt)
        
    def add_damage(self, dam):
        self.damage += dam

