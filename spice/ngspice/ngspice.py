"""
=======
Ngspice
=======

Simulation interface package for Ngspice for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
import numpy as np

class ngspice(thesdk,metaclass=abc.ABCMeta):
    """This class is used as instance in simulatormodule property of 
    spice class.
    
    """

    def __init__(self):
        pass

    @property
    def syntaxdict(self):
        """ Dictionary
        
        Internally used dictionary for syntax conversions
        """
        self._syntaxdict = {
                "cmdfile_ext" : '.ngcir',
                "resultfile_ext" : '',
                "commentchar" : '*',
                "commentline" : '***********************\n',
                "nprocflag" : 'set num_threads=', #Goes to .control section
                "simulatorcmd" : 'ngspice -b', 
                #"dcsource_declaration" : '',
                "parameter" : '.param ',
                "option" : '.option ',
                "include" : '.include',
                "dspfinclude" : '.include',
                "subckt" : '.subckt',
                "lastline" : '.end',
                "eventoutdelim" : '  ', # Two spaces
                "csvskip" : 1
                }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value

