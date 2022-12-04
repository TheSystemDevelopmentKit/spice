"""
====
Eldo
====
Eldo simulation interface package for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
import numpy as np

class eldo(thesdk,metaclass=abc.ABCMeta):
    """This class is used as instance in simulatormodule property of 
    spice class.
    
    """
    def __init__(self):
        pass

    @property
    def syntaxdict(self):
        self._syntaxdict = {
                "cmdfile_ext" : '.cir',
                "resultfile_ext" : '.wdb',
                "commentchar" : '*',
                "commentline" : '***********************\n',
                "nprocflag" : '-use_proc ', #space required
                "simulatorcmd" : 'eldo -64b',
                "dcsource_declaration" : '',
                "parameter" : '.param ',
                "option" : '.option ',
                "include" : '.include',
                "dspfinclude" : '.include',
                "subckt" : '.subckt',
                "lastline" : '.end',
                "eventoutdelim" : ' ',
                "csvskip" : 2
                }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value


