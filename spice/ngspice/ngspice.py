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
        self.print_log(type='O', msg='Syntaxdict is obsoleted. Access properties directly')
        self._syntaxdict = {
                "cmdfile_ext" : self.cmdfile_ext,
                "resultfile_ext" : self.resultfile_ext,
                "commentchar" : self.commentchar,
                "commentline" : self.commentline,
                "nprocflag" : self.nprocflag,
                "simulatorcmd" : self.simulatorcmd, 
                #"dcsource_declaration" : '',
                "parameter" : self.parameter,
                "option" : self.option,
                "include" : self.include,
                "dspfinclude" : self.dspfinclude,
                "subckt" : self.subckt,
                "lastline" : self.lastline,
                "eventoutdelim" : self.eventoutdelim, # Two spaces
                "csvskip" : self.csvskip
                }
        return self._syntaxdict
    @syntaxdict.setter
    def syntaxdict(self,value):
        self._syntaxdict=value


    @property
    def cmdfile_ext(self):
        """Extension of the command file : str
        """
        return '.ngcir'
    @property
    def resultfile_ext(self):
        """Extension of the result file : str
        """
        return ''
    @property
    def commentchar(self):
        """Comment character of the simulator : str
        """
        return '*'
    @property
    def commentline(self):
        """Comment line for the simulator : str
        """
        return '***********************\n'
    @property
    def nprocflag(self):
        """String for defining multithread execution : str
        """
        return 'set num_threads='
    @property
    def simulatorcmd(self):
        """Simulator execution command : str
        """
        return 'ngspice -b'
    @property
    def parameter(self):
        """Netlist parameter definition string : str
        """
        return '.param'
    @property
    def option(self):
        """Netlist option definition string : str
        """
        return '.option'
    @property
    def include(self):
        """Netlist include string : str
        """
        return '.include'
    @property
    def dspfinclude(self):
        """Netlist dspf-file include string : str
        """
        return '.include'
    @property
    def subckt(self):
        """Subcircuit include string : str
        """
        return '.subckt'
    @property
    def lastline(self):
        """Last line of the simulator command file : str
        """
        return '.end'
    @property
    def eventoutdelim(self):
        """Delimiter for the events : str
        """
        return '  ' #Two spaces
    @property
    def csvskip(self):
        """Needs documentation. Lines skipped in result file : int
        """
        return 1

