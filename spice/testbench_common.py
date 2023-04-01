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
        #self.dcsources=Bundle()
        self.simcmds=Bundle()
        
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

    # Generating spice options string
    @property
    def options(self):
        """str : Spice options string parsed from self.spiceoptions -dictionary in the
        parent entity.
        """
        if not hasattr(self,'_options'):
            self._options = self.testbench_simulator.options
        return self._options
    @options.setter
    def options(self,value):
        self._options=value
    @options.deleter
    def options(self,value):
        self._options=None

    @property
    def dcsources(self):
        """bundle :  bundle of DC sources inherited from parent
        """
        if not hasattr(self,'_dcsources'):
            self._dcsources = self.parent.dcsource_bundle
        return self._dcsources

    def esc_bus(self,name, esc_colon=True):
        """
        Helper function to escape bus characters for Spectre simulations::

            self.esc_bus('bus<3:0>') 
            # Returns 'bus\<3\:0\>'
        """
        # This is so simple that does not make sense to split
        if self.parent.model == 'spectre':
            if esc_colon:
                return name.replace('<','\\<').replace('>','\\>').replace('[','\\[').replace(']','\\]').replace(':','\\:')
            else: # Cannot escape colon for DC analyses..
                return name.replace('<','\\<').replace('>','\\>').replace('[','\\[').replace(']','\\]')
        else:
            return name

