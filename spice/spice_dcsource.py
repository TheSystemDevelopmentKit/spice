"""
===============
Spice DC Source
===============

Class for generating DC voltage/current sources in the Spectre or Eldo
testbench.

Initially written by Okko Järvinen, okko.jarvinen@aalto.fi, 9.1.2020

Last modification by Okko Järvinen, 23.09.2021 14:41

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

    Examples
    --------
    A voltage source connected between circuit nodes 'VDD' and 'VSS', for which
    power and current consumptions are extracted in transient simulation.
    Initiated in parent as::

        _=spice_dcsource(self,name='dd',value=1.0,extract=True,
                         pos='VDD',neg='VSS')

    A bias current flowing from 'VDD' to node 'IBIAS'::

        _=spice_dcsource(self,name='bias',sourcetype='I',value=25e-6,
                         pos='VDD',neg='IBIAS')

    Parameters
    ----------
    parent : object 
        The parent object initializing the `spice_dcsource` instance. Default
        None.
    
    **kwargs :  
            name: str
                Name of the source.
            value: float
                Value of the source.
            sourcetype: str
                Type of the DC source. Either 'V' for voltage or 'I' for
                current.
            extract: bool
                Flag the source for transient current and power consumption
                extraction. Extracted currents and powers are accessible
                through dictionaries self.currents and self.powers in the
                parent object. Default False.
            ext_start: float
                Time to start extracting average transient power consumption.
                Default is 0.
            ext_stop: float
                Time to stop extracting average transient power consumption.
                Default is simulation end time.
            pos: str
                Name of the positive node in the ELDO netlist.
            neg: str
                Name of the negative node in the ELDO netlist.
            noise: bool
                Enable the noise contribution of this source (only when
                transient noise is enabled). Default is True.
            ramp: float
                Ramp up the source from 0 to value in ramp seconds. Default is
                0 (no ramping).
    
    """

    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,parent,**kwargs):
        try:  
            self.parent = parent
            self._sourcetype=kwargs.get('sourcetype','V')
            self._name=kwargs.get('name','sourcename')
            self._pos=kwargs.get('pos','POSNODE')
            self._neg=kwargs.get('neg','NEGNODE')
            self._value=kwargs.get('value',0)
            self._extract=kwargs.get('extract',False)
            self._ext_start=kwargs.get('ext_start',None)
            self._ext_stop=kwargs.get('ext_stop',None)
            self._noise=kwargs.get('noise',True)
            self._ramp=kwargs.get('ramp',0)

        except:
            self.print_log(type='F', msg="Spice DC source definition failed.")

        if hasattr(self.parent,'dcsource_bundle'):
            self.parent.dcsource_bundle.new(name=self.name,val=self)

    @property
    def sourcetype(self):
        """Set by argument 'sourcetype'."""
        if hasattr(self,'_sourcetype'):
            return self._sourcetype
        else:
            self._sourcetype='V'
        return self._sourcetype
    @sourcetype.setter
    def sourcetype(self,value):
        self._sourcetype=value

    @property
    def name(self):
        """Set by argument 'name'."""
        if hasattr(self,'_name'):
            return self._name
        else:
            self._name='sourcename'
        return self._name
    @name.setter
    def name(self,value):
        self._name=value

    @property
    def neg(self):
        """Set by argument 'neg'."""
        if hasattr(self,'_neg'):
            return self._neg
        else:
            self._neg='NEGNODE'
        return self._neg
    @neg.setter
    def neg(self,neg):
        self._neg=neg

    @property
    def pos(self):
        """Set by argument 'pos'."""
        if hasattr(self,'_pos'):
            return self._pos
        else:
            self._pos='POSNODE'
        return self._pos
    @pos.setter
    def pos(self,pos):
        self._pos=pos

    @property
    def value(self):
        """Set by argument 'value'."""
        if hasattr(self,'_value'):
            return self._value
        else:
            self._value='0'
        return self._value
    @value.setter
    def value(self,value):
        self._value=value

    @property
    def extract(self):
        """Set by argument 'extract'."""
        if hasattr(self,'_extract'):
            return self._extract
        else:
            self._extract=False
        return self._extract
    @extract.setter
    def extract(self,value):
        self._extract=value

    @property
    def ext_start(self):
        """Set by argument 'ext_start'."""
        if hasattr(self,'_ext_start'):
            return self._ext_start
        else:
            self._ext_start=None
        return self._ext_start
    @ext_start.setter
    def ext_start(self,value):
        self._ext_start=str(value)

    @property
    def ext_stop(self):
        """Set by argument 'ext_stop'."""
        if hasattr(self,'_ext_stop'):
            return self._ext_stop
        else:
            self._ext_stop=None
        return self._ext_stop
    @ext_stop.setter
    def ext_stop(self,value):
        self._ext_stop=str(value)

    @property
    def noise(self):
        """Set by argument 'noise'."""
        if hasattr(self,'_noise'):
            return self._noise
        else:
            self._noise=False
        return self._noise
    @noise.setter
    def noise(self,value):
        self._noise=value

    @property
    def ramp(self):
        """Set by argument 'ramp'."""
        if hasattr(self,'_ramp'):
            return self._ramp
        else:
            self._ramp=0
        return self._ramp
    @ramp.setter
    def ramp(self,value):
        self._ramp=value
