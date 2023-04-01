"""
=================
Spectre Testbench
=================

Simulators sepecific testbench generation class for Spectre.

"""
import os
import sys
import subprocess
import shlex
import fileinput

from thesdk import *
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
            self._options = "%s Options\n" % self.parent.spice_simulator.commentchar
            if self.parent.postlayout and 'savefilter' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option savefilter=rc for post-layout netlists to reduce output file size!')
            if self.parent.postlayout and 'save' not in self.parent.spiceoptions:
                self.print_log(type='I', msg='Consider using option save=none and specifiying saves with plotlist for post-layout netlists to reduce output file size!')
            i=0
            for optname,optval in self.parent.spiceoptions.items():
                self._options += "Option%d " % i # spectre options need unique names
                i+=1
                if optval != "":
                    self._options += self.parent.spice_simulator.option + ' ' + optname + "=" + optval + "\n"
                else:
                    self._options += ".option " + optname + "\n"

        return self._options
    @options.setter
    def options(self,value):
        self._options=value

    @property
    def libcmd(self):
        """str : Library inclusion string. Parsed from self.spicecorner -dictionary in
        the parent entity, as well as 'ELDOLIBFILE' or 'SPECTRELIBFILE' global
        variables in TheSDK.config.
        """
        if not hasattr(self,'_libcmd'):
            libfile = ""
            corner = "top_tt"
            temp = "27"
            for optname,optval in self.parent.spicecorner.items():
                if optname == "temp":
                    temp = optval
                if optname == "corner":
                    corner = optval
            try:
                libfile = thesdk.GLOBALS['SPECTRELIBFILE']
                if libfile == '':
                    raise ValueError
                else:
                    self._libcmd = "// Spectre device models\n"
                    files = libfile.split(',')
                    if len(files)>1:
                        if isinstance(corner,list) and len(files) == len(corner):
                            for path,corn in zip(files,corner):
                                if not isinstance(corn, list):
                                    corn = [corn]
                                for c in corn:
                                    self._libcmd += 'include "%s" section=%s\n' % (path,c)
                        else:
                            self.print_log(type='W',msg='Multiple entries in SPECTRELIBFILE but spicecorner wasn\'t a list or contained different number of elements!')
                            self._libcmd += 'include "%s" section=%s\n' % (files[0], corner)
                    else:
                        self._libcmd += 'include "%s" section=%s\n' % (files[0], corner)
            except:
                self.print_log(type='W',msg='Global TheSDK variable SPECTRELIBPATH not set.')
                self._libcmd = "// Spectre device models (undefined)\n"
                self._libcmd += "//include " + libfile + " " + corner + "\n"
            self._libcmd += 'tempOption options temp=%s\n' % str(temp)
        return self._libcmd
    @libcmd.setter
    def libcmd(self,value):
        self._libcmd=value
    @libcmd.deleter
    def libcmd(self,value):
        self._libcmd=None

