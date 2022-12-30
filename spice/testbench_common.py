"""
===============
Spice Testbench
===============

Testbench generation class for spice simulations.

"""
import os
import sys
import subprocess
import shlex
import fileinput
from abc import * 
from thesdk import *
from spice import *
from spice.spice_module import spice_module
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime

class testbench_common(spice_module):
    """
    This class generates all testbench contents.
    This class is utilized by the main spice class.

    """

    def __init__(self, parent=None, **kwargs):
        if parent==None:
            self.print_log(type='F', msg="Parent of spice testbench not given.")
        else:
            self.parent=parent
        try:  
            self._file=self.parent.spicetbsrc # Testbench
            self._subcktfile=self.parent.spicesubcktsrc # Parsed subcircuit file
            self._dutfile=self.parent.spicesrc # Source netlist file
            # This attribute holds duration of longest input vector after reading input files
            self._trantime=0
        except:
            self.print_log(type='F', msg="Spice Testbench file definition failed.")
        
        #The methods for these are derived from spice_module
        self._name=''
        self.iofiles=Bundle()
        self.dcsources=Bundle()
        self.simcmds=Bundle()
        
    @property
    def file(self):
        """String
        
        Filepath to the testbench file (i.e. './spice/tb_entityname.scs').
        """
        if not hasattr(self,'_file'):
            self._file=None
        return self._file
    @file.setter
    def file(self,value):
            self._file=value

    @property
    def header(self):
        """The header of the testbench

        """
        if not hasattr(self,'_header'):
            date_object = datetime.now()
            self._header = self.parent.spice_simulator.commentline +\
                    "%s Testbench for %s\n" % (self.parent.spice_simulator.commentchar,self.parent.name) +\
                    "%s Generated on %s \n" % (self.parent.spice_simulator.commentchar,date_object) +\
                    self.parent.spice_simulator.commentline
            return self._header

