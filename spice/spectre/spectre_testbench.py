"""
=================
Ngspice Testbench
=================

Simulators sepecific testbench generation class for Ngspice.

"""
import os
import sys
import subprocess
import shlex
import fileinput
from spice.testbench_common import testbench_common
import pdb

import numpy as np
import pandas as pd
from functools import reduce
import textwrap
from datetime import datetime

class spectre_testbench(testbench_common):
    def __init__(self, parent=None, **kwargs):
        ''' Executes init of testbench_common, thus having the same attributes and 
        parameters.

        Parameters
        ----------
            **kwargs :
               See module testbench_common
        
        '''
        super().__init__(parent=parent,**kwargs)

    # Generating spice options string
    @property
    def options(self):
        """String
        
        Spice options string parsed from self.spiceoptions -dictionary in the
        parent entity.
        """
        if not hasattr(self,'_options'):
            self._options = "%s Options\n" % self.parent.syntaxdict["commentchar"]
            if self.postlayout and 'savefilter' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option savefilter=rc for post-layout netlists to reduce output file size!')
            if self.postlayout and 'save' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option save=none and specifiying saves with plotlist for post-layout netlists to reduce output file size!')
            i=0
            for optname,optval in self.parent.spiceoptions.items():
                self._options += "Option%d " % i # spectre options need unique names
                i+=1
                if optval != "":
                    self._options += self.parent.syntaxdict["option"] + optname + "=" + optval + "\n"
                else:
                    self._options += ".option " + optname + "\n"

        return self._options
    @options.setter
    def options(self,value):
        self._options=value

