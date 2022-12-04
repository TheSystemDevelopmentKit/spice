"""
=======
Spectre
=======
Spectre simulation interface package for Spectre for TheSyDeKick.

Initially written by Okko Järvinen, 2019
"""
import os
import sys
from abc import * 
from thesdk import *
import numpy as np

class spectre(thesdk,metaclass=abc.ABCMeta):
    """This class is used as instance in simulatormodule property of 
    spice class.
    
    """
    def __init__(self):
        pass

    @property
    def syntaxdict(self):
        self._syntaxdict = {
                "cmdfile_ext" : '.scs',
                "resultfile_ext" : '.raw',
                "commentchar" : '//',
                "commentline" : '///////////////////////\n',
                "nprocflag" : '+mt=', #space required??
                "simulatorcmd" : 'spectre',
                "dcsource_declaration" : 'vsource type=dc dc=',
                "parameter" : 'parameters ',
                "option" : 'options ',
                "include" : 'include ',
                "dspfinclude" : 'dspf_include ',
                "subckt" : 'subckt',
                "lastline" : '///', #needed?
                "eventoutdelim" : ',',
                "csvskip" : 0
                }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value

