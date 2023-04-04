"""
============
Spice Common
============

Mix-in class of ommon properties and methods for spice simulator classes

"""
import os
import sys
import subprocess
import shlex
import fileinput
from thesdk import *
from spice.spice_methods import spice_methods
import pdb

class spice_common(spice_methods,thesdk):
    """
    Common properties and methods for spice simulator tool classes.
    Most of these are overloaded in __init__.py

    """

    @property
    def extracts(self):
        """ Bundle

        A thesdk.Bundle containing extracted quantities.
        """
        if not hasattr(self,'_extracts'):
            self._extracts=Bundle()
        return self._extracts
    @extracts.setter
    def extracts(self,value):
        self._extracts=value

    #### [TODO] To be relocated
    # Strobing related stuff should not be in this class. Maybe spice_iofile or 
    # testbench also suposedly these are spectre specific
    @property
    def strobe_indices(self):
        """
        Internally set list of indices corresponding to time,amplitude pairs
        whose time value of is a multiple of the strobeperiod (see spice_simcmd).
        """
        if not hasattr(self,'_strobe_indices'):
            self._strobe_indices=[]
        return self._strobe_indices

    @strobe_indices.setter
    def strobe_indices(self,val):
        if isinstance(val, list) or isinstance(val, np.ndarray):
            self._strobe_indices=val
        else:
            self.print_log(type='W', msg='Cannot set strobe_indices to be of type: %s' % type(val))

    @property
    def is_strobed(self):
        '''
        Check if simulation was strobed or not
        '''
        if not hasattr(self, '_is_strobed'):
            self._is_strobed=False
            for simtype, simcmd in self.simcmd_bundle.Members.items():
                if simtype=='tran':
                    if simcmd.strobeperiod:
                        self._is_strobed=True
        return self._is_strobed

