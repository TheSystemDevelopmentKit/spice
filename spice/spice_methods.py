"""
Spice methods

Collection of methods provided as a mixin class

Initially restructured to this package Marko Kosunen 2022
"""


import os
import sys
from abc import * 
from thesdk import *

class spice_methods:

    def filter_strobed(self, key,ioname):
        """
        Helper function to read in the strobed simulation results. Only for spectre.

        TODO:
        this is because the strobeoutput
        parameter for some reason still outputs
        all the data points, even when it is in mode
        strobeonly
        If solution is found to this later from simulator
        remove this.
        """
        if len(self.strobe_indices)==0:
            tvals=self.iofile_eventdict[ioname.upper()][:,0]
            maxtime = np.max(tvals)
            mintime = np.min(tvals)
            for simulationcommand, simulationoption in self.simcmd_bundle.Members.items():
                strobeperiod = simulationoption.strobeperiod
                strobedelay = simulationoption.strobedelay
                skipstart = simulationoption.skipstart
            if not skipstart:
                skipstart=0
            if not strobedelay:
                strobedelay=0
            strobetimestamps = np.arange(mintime,maxtime,strobeperiod)+strobedelay+skipstart
            self.strobe_indices=np.zeros(len(strobetimestamps)) # indexes to take the values
            seg=min(300, len(strobetimestamps)) # length of a segment in the for loop (how many samples at a time)
            idxmin=0
            l=len(strobetimestamps)
            nseg=l//seg # number of segments, rounded down (how many loops required)
            idxmax=0
            i = 0
            for i in np.arange(1,nseg):
                idxmax=(i-1)*seg+np.argmin(abs(tvals[(i-1)*seg:]-strobetimestamps[i*seg])) # find index of the received signal which corresponds to the largest value in reference
                ind=idxmin+abs(strobetimestamps[seg*(i-1):seg*(i),None]-tvals[None,idxmin:idxmax]).argmin(axis=-1) # take index for the seg's values
                idxmin=idxmax
                self.strobe_indices[seg*(i-1):seg*i]=ind  
            # again just in case that the loop does not overflow to take the final samples into account
            idxmax=len(tvals)-1
            ind=idxmin+abs(strobetimestamps[seg*(i):,None]-tvals[None,idxmin:idxmax]).argmin(axis=-1)
            idxmin=idxmax
            self.strobe_indices[seg*(i):]=ind
            self.strobe_indices=self.strobe_indices.astype(int)
            if self.iofile_bundle.Members[key].strobe:
                new_array =self.iofile_eventdict[ioname.upper()][self.strobe_indices]
                if len(strobetimestamps)!=len(new_array):
                    self.print_log(type='W',
                            msg='Oh no, something went wrong while reading the strobeperiod data')
                    self.print_log(type='W',
                            msg='Check data lenghts!')
            else:
                new_array =self.iofile_eventdict[ioname.upper()]
        else: # We already know the strobe indices, use them!
            if self.iofile_bundle.Members[key].strobe:
                new_array =self.iofile_eventdict[ioname.upper()][self.strobe_indices]
            else:
                new_array =self.iofile_eventdict[ioname.upper()]
        return new_array

    def check_output_accuracy(self,key):
        '''
        Helper function to check output accuracy
        '''
        try:
            tdiff = np.diff(self.iofile_eventdict[key.upper()][:,0])
            if np.any(tdiff == 0.0):
                    self.print_log(type='W', msg='Accuracy of output file is insufficient. Increase value of \'digits\' parameter and re-run simulation!')
        except: # Requested output wasn't in output file, do nothing
            self.print_log(type='W',msg='Couldn\'t check output file accuracy')
            self.print_log(type='W',msg=traceback.format_exc())


    def get_buswidth(self,signame):
        """ Extract buswidth from signal name.
        
        Little-endian example::
                
            start,stop,width,busrange = get_buswidth('BUS<10:0>')
            # start = 10
            # stop = 0
            # width = 11
            # busrange = range(10,-1,-1)

        Big-endian example::
                
            start,stop,width,busrange = get_buswidth('BUS<0:8>')
            # start = 0
            # stop = 8
            # width = 9
            # busrange = range(0,9)
            
        """
        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
        if '' in signame:
            signame.remove('')
        if len(signame) == 1:
            busstart = 0
            busstop = 0
        elif len(signame) == 2:
            busstart = int(signame[1])
            busstop = int(signame[1])
        else:
            busstart = int(signame[1])
            busstop = int(signame[2])
        if busstart > busstop:
            buswidth = busstart-busstop+1
            busrange = range(busstart,busstop-1,-1)
        else:
            buswidth = busstop-busstart+1
            busrange = range(busstart,busstop+1)
        return busstart,busstop,buswidth,busrange
    
    def si_string_to_float(self, strval):
        """ Convert SI-formatted string to float
            
        E.g. self.si_string_to_float('3 mV') returns 3e-3.
        """
        parts = strval.split()
        if len(parts) == 2:
            val = float(parts[0])
            if len(parts[1]) == 1: # No prefix
                mult = 1
            else:
                try:
                    mult = self.si_prefix_mult[parts[1][0]]
                except KeyError: # Could not convert, just return the text value
                    self.print_log(type='W', msg='Invalid SI-prefix %s, failed to convert.' % parts[1][0])
                    return strval
            return val*mult
        else:
            return strval # Was a text value


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

