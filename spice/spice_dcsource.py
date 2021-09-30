"""
===============
Spice DC Source
===============

Class for generating DC voltage/current sources in the Spectre or Eldo
testbench.

Initially written by Okko Järvinen, 9.1.2020

"""

import os
import sys
from abc import * 
from thesdk import *
from thesdk.iofile import iofile
import numpy as np
import pandas as pd

class spice_dcsource(thesdk):
    """
    Class to provide DC source definitions to spice testbench.  When
    instantiated in the parent class, this class automatically attaches
    spice_dcsource objects to dcsource_bundle -bundle in testbench.

    Parameters
    ----------
    parent : object 
        The parent object initializing the spice_dcsource instance. Default
        None.
    name : str
        Name of the source.
    value : float
        Value of the source.
    sourcetype : 'V' or 'I'
        Type of the DC source. Either 'V' for voltage or 'I' for current.
    pos : str
        Name of the positive net in the netlist.
    neg : str
        Name of the negative net in the netlist.
    extract : bool
        Flag the source for transient current and power consumption extraction.
        Extracted currents and powers are accessible through dictionaries
        self.currents and self.powers in the parent object. Default False.
    ext_start : float
        Time to start extracting average transient power consumption. Default
        is 0.
    ext_stop : float
        Time to stop extracting average transient power consumption. Default
        is simulation end time.
    noise : bool
        Enable the noise contribution of this source (only when transient noise
        is enabled). Default is True.
    ramp : float
        Ramp up the source from 0 to value in ramp seconds. Default is 0 (no
        ramping).

    Examples
    --------
    A voltage source connected between circuit nodes 'VDD' and 'VSS', for which
    power and current consumptions are extracted in transient simulation.
    Initiated in parent as::

        _=spice_dcsource(self,name='supply',value=1.0,extract=True,pos='VDD',neg='VSS')
        _=spice_dcsource(self,name='ground',value=0,pos='VSS',neg='0') # Ground 'source'

    A bias current flowing from 'VDD' to node 'IBIAS'::

        _=spice_dcsource(self,name='bias',sourcetype='I',value=25e-6,pos='VDD',neg='IBIAS')

    """

    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,parent,**kwargs):
        try:  
            self.parent = parent
            self.sourcetype=kwargs.get('sourcetype','V')
            self.name=kwargs.get('name','sourcename')
            self.pos=kwargs.get('pos','POSNODE')
            self.neg=kwargs.get('neg','NEGNODE')
            self.value=kwargs.get('value',0)
            self.extract=kwargs.get('extract',False)
            self.ext_start=kwargs.get('ext_start',None)
            self.ext_stop=kwargs.get('ext_stop',None)
            self.noise=kwargs.get('noise',True)
            self.ramp=kwargs.get('ramp',0)
        except:
            self.print_log(type='F', msg="Spice DC source definition failed.")

        if hasattr(self.parent,'dcsource_bundle'):
            self.parent.dcsource_bundle.new(name=self.name,val=self)

    @property
    def ext_file(self):
        """String

        Optional filepath for extracted transient current when
        self.extract=True.
        """
        if not hasattr(self,'_ext_file'):
            self._ext_file = '%s/tb_%s.print' % (self.parent.spicesimpath,self.parent.name)
        return self._ext_file
    @ext_file.setter
    def ext_file(self,val):
        self._ext_file=val
        return self._ext_file
