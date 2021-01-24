"""
=============
Spice IO-file
=============

Provides spice file IO related attributes and methods 
for TheSDK spice.

Initially written by Okko Järvinen, okko.jarvinen@aalto.fi, 9.1.2020

Last modification by Okko Järvinen, 07.10.2020 14:40

"""
import os
import sys
import pdb
from abc import * 
from thesdk import *
from thesdk.iofile import iofile
import numpy as np
import pandas as pd
from numpy import genfromtxt
#from spice.connector import intend
import traceback

class spice_iofile(iofile):
    """
    Class to provide file IO for spice simulations. When created, 
    adds a spice_iofile object to the parents iofile_bundle attribute.
    Accessible as iofile_bundle.Members['name'].

    Examples
    --------
    Initiated in parent as::

        _=spice_iofile(self,name='foobar')

    Defining analog input voltage signals from python to spice::

        _=spice_iofile(self,name='inp',dir='in',iotype='event',sourcetype='V',ionames='INP')
        _=spice_iofile(self,name='inn',dir='in',iotype='event',sourcetype='V',ionames='INN')

    Defining time-domain output signal containing rising edge threshold
    crossing timestamps of an analog clock signal::

        _=spice_iofile(self,name='clk_rise',dir='out',iotype='time',sourcetype='V',
                       ionames='CLK',edgetype='rising',vth=self.vdd/2)

    Defining digital output signal triggered with a falling edge of the analog clock::

        _=spice_iofile(self,name='dout',dir='out',iotype='sample',sourcetype='V',
                       ionames='DOUT<7:0>',edgetype='falling',vth=self.vdd/2,trigger='CLK')

    Defining digital input signal with decimal format. The input vector is a
    list of integers, which get converted to binary bus of 4-bits (inferred
    from 'CTRL<3:0>'). The values are changed at 1 MHz interval in this
    example.::

        _=spice_iofile(self,name='ctrl',dir='in',iotype='sample',ionames='CTRL<3:0>',rs=1e6,
                       vhi=self.vdd,trise=5e-12,tfall=5e-12,ioformat='dec')
        
    Parameters
    -----------
    parent : object 
        The parent object initializing the 
        spice_iofile instance. Default None
    
    **kwargs :  
            name (str)
                Name of the IO.
            ioformat (str)
                Formatting of the IO signal: 'dec'/'bin'.
                Default 'dec'.
            dir (str)
                Direction of the IO: 'in'/'out'.
            iotype (str)
                Type of the IO signal: 'event'/'sample'/'time'.
                Event type signals are time-value pairs (analog signal),
                while sample type signals are sampled by a clock signal (digital bus).
                Time type signals return a vector of timestamps corresponding
                to threshold crossings.
            datatype (str)
                Datatype, not yet implemented.
            trigger (str or list<str>)
                Name of the clock signal node in the Spice netlist.
                If a single string is given, the same clock signal is used for all bits/buses.
                If a list is given, and the length matches ionames list length, each ioname will
                be assigned its own clock.
                Applies only to sample type outputs.
            vth (float)
                Threshold voltage of the trigger signal and the bit rounding.
                Applies only to sample type outputs.
            edgetype (str)
                Type of triggering edge: 'rising'/'falling'/'both'.
                When time type signal is used, the edgetype values can define the
                extraction type as: 'rising'/'falling'/'both'/'risetime'/'falltime'.
                Default 'rising'.
            after (float)
                Time to wait before starting the extraction (useful for ignoring inital settling).
                Applies only to sample type outputs.
                Default 0.
            big_endian (bool)
                Flag to read the extracted bus as big-endian.
                Applies only to sample type outputs.
                Default False.
            rs (float)
                Sample rate of the sample type input.
                Default None.
            vhi (float)
                High bit value of sample type input.
                Default 1.0.
            vlo (float)
                Low bit value of sample type input.
                Default 0.
            tfall (float)
                Falltime of sample type input.
                Default 5e-12.
            trise (float)
                Risetime of sample type input.
                Default 5e-12.
    """
    def __init__(self,parent=None,**kwargs):
        if parent==None:
            self.print_log(type='F', msg="Parent of spice input file not given")
        try:  
            super(spice_iofile,self).__init__(parent=parent,**kwargs)
            self.paramname=kwargs.get('param','-g g_file_')
            self._ioformat=kwargs.get('ioformat','dec') #by default, the io values are decimal integer numbers
            self._trigger=kwargs.get('trigger','')
            self._vth=kwargs.get('vth',0.5)
            self._edgetype=kwargs.get('edgetype','rising')
            self._after=kwargs.get('after',0)
            self._big_endian=kwargs.get('big_endian',False)
            self._rs=kwargs.get('rs',None)
            self._vhi=kwargs.get('vhi',1.0)
            self._vlo=kwargs.get('vlo',0)
            self._tfall=kwargs.get('tfall',5e-12)
            self._trise=kwargs.get('trise',5e-12)
            if kwargs.get('dir') == 'out':
                self.print_log(type='W', msg="The output results will no longer be appended to file (i.e. are overwritten) as of v1.6!")
        except:
            self.print_log(type='F', msg="spice IO file definition failed.")

    @property
    def ioformat(self):
        """Set by argument 'ioformat'."""
        if hasattr(self,'_ioformat'):
            return self._ioformat
        else:
            self._ioformat='dec'
        return self._ioformat
    @ioformat.setter
    def ioformat(self,value):
        self._ioformat=value

    @property
    def trigger(self):
        """Set by argument 'trigger'."""
        if hasattr(self,'_trigger'):
            return self._trigger
        else:
            self._trigger=""
            self.print_log(type='F',msg='Trigger node not given.')
        return self._trigger
    @trigger.setter
    def trigger(self,value):
        self._trigger=value

    @property
    def vth(self):
        """Set by argument 'vth'."""
        if hasattr(self,'_vth'):
            return self._vth
        else:
            self._vth=0.5
        return self._vth
    @vth.setter
    def vth(self,value):
        self._vth=value

    @property
    def edgetype(self):
        """Set by argument 'edgetype'."""
        if hasattr(self,'_edgetype'):
            return self._edgetype
        else:
            self._edgetype='rising'
        return self._edgetype
    @edgetype.setter
    def edgetype(self,value):
        self._edgetype=value

    @property
    def after(self):
        """Set by argument 'after'."""
        if hasattr(self,'_after'):
            return self._after
        else:
            self._after=0
        return self._after
    @after.setter
    def after(self,value):
        self._after=value

    @property
    def big_endian(self):
        """Set by argument 'big_endian'."""
        if hasattr(self,'_big_endian'):
            return self._big_endian
        else:
            self._big_endian=False
        return self._big_endian
    @big_endian.setter
    def big_endian(self,value):
        self._big_endian=value

    @property
    def rs(self):
        """Set by argument 'rs'."""
        if hasattr(self,'_rs'):
            return self._rs
        else:
            self._rs=None
        return self._rs
    @rs.setter
    def rs(self,value):
        self._rs=value

    @property
    def vhi(self):
        """Set by argument 'vhi'."""
        if hasattr(self,'_vhi'):
            return self._vhi
        else:
            self._vhi=1.0
        return self._vhi
    @vhi.setter
    def vhi(self,value):
        self._vhi=value

    @property
    def vlo(self):
        """Set by argument 'vlo'."""
        if hasattr(self,'_vlo'):
            return self._vlo
        else:
            self._vlo=0
        return self._vlo
    @vlo.setter
    def vlo(self,value):
        self._vlo=value

    @property
    def tfall(self):
        """Set by argument 'tfall'."""
        if hasattr(self,'_tfall'):
            return self._tfall
        else:
            self._tfall=5e-12
        return self._tfall
    @tfall.setter
    def tfall(self,value):
        self._tfall=value

    @property
    def trise(self):
        """Set by argument 'trise'."""
        if hasattr(self,'_trise'):
            return self._trise
        else:
            self._trise=5e-12
        return self._trise
    @trise.setter
    def trise(self,value):
        self._trise=value

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

    # Overloading file property to contain a list
    @property
    def file(self):
        """List<str>

        List containing filepaths to files associated with this spice_iofile.
        For digital buses or arrays of signals, the list contains multiple
        files which are automatically handled together. These filepaths are set
        automatically.
        """
        self._file = []
        for ioname in self.ionames:
            filename = self.parent.spicesimpath+'/'
            if self.parent.model == 'ngspice' and self.dir == 'in':
                filename += ('%s_%s_%s%s.txt' % (self.parent.runname,ioname.replace('<','').replace('>','').replace('.','_'),self.iotype,('_%s' % self.edgetype if self.iotype is not 'event' else ''))).lower()
            else:
                filename += ('%s_%s_%s%s.txt' % (self.parent.runname,ioname.replace('<','').replace('>','').replace('.','_'),self.iotype,('_%s' % self.edgetype if self.iotype is not 'event' else '')))

            self._file.append(filename)
        return self._file
    @file.setter
    def file(self,val):
        self._file=val
        return self._file

    # Overloading ionames property to contain a list
    @property
    def ionames(self):
        """List<str>

        Set by argument 'ionames'. This property casts the given argument to a
        list if needed.
        """
        if isinstance(self._ionames,str):
            self._ionames = [self._ionames]
        return self._ionames
    @ionames.setter
    def ionames(self,val):
        self._ionames=val
        return self._ionames

    # Overloading the remove functionality to remove tmp files
    def remove(self):
        """
        Function to remove files associated with this spice_iofile.
        """
        if self.preserve:
            self.print_log(type='I', msg='Preserving files for %s.' % self.name)
        else:
            try:
                self.print_log(type='I',msg='Removing files for %s.' % self.name)
                for f in self.file:
                    if os.path.exists(f):
                        os.remove(f)
            except:
                self.print_log(type='E',msg=traceback.format_exc())
                self.print_log(type='W',msg='Failed while removing files for %s.' % self.name)

    # Overloaded write from thesdk.iofile
    def write(self,**kwargs):
        """
        Function to write files associated with this spice_iofile.
        """
        if self.iotype == 'event':
            try:
                data = self.Data
                for i in range(len(self.file)):
                    np.savetxt(self.file[i],data[:,[2*i,2*i+1]],delimiter=',')
                    self.print_log(type='I',msg='Writing input file: %s.' % self.file[i])
            except:
                    self.print_log(type='E',msg=traceback.format_exc())
                    self.print_log(type='E',msg='Failed while writing files for %s.' % self.file[i])
        elif self.iotype == 'sample':
            try:
                for i in range(len(self.file)):
                    self.print_log(type='I',msg='Writing digital input file: %s.' % self.file[i])
                    if not isinstance(self.Data,int):
                        # Input is a vector
                        vec = self.Data[:,i]
                    else:
                        # Input is a scalar value
                        vec = [self.Data]
                    # Extracting the bus width
                    signame = self.ionames[i]
                    signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
                    if len(signame) == 1:
                        busstart = 0
                        busstop = 0
                    else:
                        busstart = int(signame[1])
                        busstop = int(signame[2])
                    if busstart > busstop:
                        buswidth = busstart-busstop+1
                    else:
                        buswidth = busstop-busstart+1
                with open(self.file[i],'w') as outfile:
                    if self.parent.model == 'spectre':
                        # This is Spectre vector file syntax
                        outfile.write('radix %s\n' % ('1 '*buswidth))
                        outfile.write('io i\n')
                        outfile.write('vname %s\n' % self.ionames[i].replace('<','<[').replace('>',']>'))
                        outfile.write('tunit ns\n')
                        outfile.write('period %g\n' % (1e9/float(self.rs)))
                        outfile.write('trise %g\n' % (float(self.trise)*1e9))
                        outfile.write('tfall %g\n' % (float(self.tfall)*1e9))
                        outfile.write('tdelay %g\n' % (float(self.after)*1e9))
                        outfile.write('vih %g\n' % self.vhi)
                        outfile.write('vil %g\n\n' % self.vlo)
                        for j in range(len(vec)):
                            if self.ioformat == 'dec':
                                # Input values are integer numbers (TODO: check if its unsigned)
                                binary = format(vec[j],'0%db' % buswidth)
                            else:
                                # Input values  are bits (strings of '1' and '0')
                                binary = vec[j]
                            outfile.write('%s\n' % binary)
                    if self.parent.model == 'ngspice':
                        # This is Ngsim vector file syntax
                        for j in range(len(vec)):
                            if self.ioformat == 'dec':
                                # Input values are integer numbers (TODO: check if its unsigned)
                                binary = format(vec[j],'0%db' % buswidth)
                            else:
                                # Input values  are bits (strings of '1' and '0')
                                binary = vec[j]
                            line = str(j/self.rs)+' '+'s '.join(binary)+'s'
                            outfile.write('%s\n' % line)
            except:
                self.print_log(type='E',msg=traceback.format_exc())
                self.print_log(type='E',msg='Failed while writing files for %s.' % self.file[i])
        else:
            pass

    # Overloaded read from thesdk.iofile
    def read(self,**kwargs):
        """
        Function to read files associated with this spice_iofile.
        """
        for i in range(len(self.file)):
            try:
                if self.iotype=='event' or self.iotype=='vsample':
                    arr = genfromtxt(self.file[i],delimiter=self.parent.syntaxdict['eventoutdelim'], \
                            skip_header=self.parent.syntaxdict['csvskip'])
                    if self.Data is None: 
                        self.Data = np.array(arr)
                    else:
                        self.Data = np.hstack((self.Data,np.array(arr)))
                    # TODO: verify csvskip
                elif self.iotype=='time':
                    #if self.parent.model == 'eldo':
                    #    nodematch=re.compile(r"%s" % self.ionames[i].upper())
                    #    with open(self.file[i]) as infile:
                    #        wholefile=infile.readlines()
                    #        arr = []
                    #        for line in wholefile:
                    #            if nodematch.search(line) != None:
                    #                arr.append(float(line.split()[-1]))
                    #        nparr = np.array(arr).reshape(-1,1)
                    #        if self.Data is None: 
                    #            self.Data = nparr
                    #        else:
                    #            if len(self.Data[:,-1]) > len(nparr):
                    #                # Old max length is bigger -> padding new array
                    #                nans = np.empty(self.Data[:,-1].shape).reshape(-1,1)
                    #                nans.fill(np.nan)
                    #                nans[:nparr.shape[0],:nparr.shape[1]] = nparr
                    #                nparr = nans
                    #            elif len(self.Data[:,-1]) < len(nparr):
                    #                # Old max length is smaller -> padding old array
                    #                nans = np.empty((nparr.shape[0],self.Data.shape[1]))
                    #                nans.fill(np.nan)
                    #                nans[:self.Data.shape[0],:self.Data.shape[1]] = self.Data
                    #                self.Data = nans
                    #            self.Data = np.hstack((self.Data,nparr))
                    #    infile.close()
                    #elif self.parent.model == 'spectre':

                    # This should work for both spectre and eldo now
                    arr = genfromtxt(self.file[i],delimiter=', ',skip_header=self.parent.syntaxdict["csvskip"])
                    if self.edgetype.lower() == 'both':
                        trise = self.interp_crossings(arr,self.vth,256,'rising')
                        tfall = self.interp_crossings(arr,self.vth,256,'falling')
                        tcross = np.sort(np.vstack((trise.reshape(-1,1),tfall.reshape(-1,1))),0)
                    else:
                        tcross = self.interp_crossings(arr,self.vth,256,self.edgetype)
                    nparr = np.array(tcross).reshape(-1,1)
                    if self.Data is None: 
                        self.Data = nparr
                    else:
                        if len(self.Data[:,-1]) > len(nparr):
                            # Old max length is bigger -> padding new array
                            nans = np.empty(self.Data[:,-1].shape).reshape(-1,1)
                            nans.fill(np.nan)
                            nans[:nparr.shape[0],:nparr.shape[1]] = nparr
                            nparr = nans
                        elif len(self.Data[:,-1]) < len(nparr):
                            # Old max length is smaller -> padding old array
                            nans = np.empty((nparr.shape[0],self.Data.shape[1]))
                            nans.fill(np.nan)
                            nans[:self.Data.shape[0],:self.Data.shape[1]] = self.Data
                            self.Data = nans
                        self.Data = np.hstack((self.Data,nparr))
                elif self.iotype=='sample':
                    if self.parent.model == 'eldo':
                        nodematch=re.compile(r"%s" % self.ionames[i].upper())
                        with open(self.file[i]) as infile:
                            wholefile=infile.readlines()
                            maxsamp = -1
                            outbus = {}
                            for line in wholefile:
                                if nodematch.search(line) != None:
                                    tokens = re.findall(r"[\w']+",line)
                                    bitidx = tokens[2]
                                    sampidx = tokens[3]
                                    if int(sampidx) > maxsamp:
                                        maxsamp = int(sampidx)
                                    bitval = line.split()[-1]
                                    # TODO: Rounding to bits is done here (might need to go elsewhere)
                                    # Also, not all sampled signals need to be output as bits necessarily
                                    if float(bitval) >= self.vth:
                                        bitval = '1'
                                    else:
                                        bitval = '0'
                                    if bitidx in outbus.keys():
                                        outbus[bitidx].append(bitval)
                                    else:
                                        outbus.update({bitidx:[bitval]})
                            maxbit = max(map(int,outbus.keys()))
                            minbit = min(map(int,outbus.keys()))
                            # TODO: REALLY check the endianness of these (together with RTL)
                            if not self.big_endian:
                                bitrange = range(maxbit,minbit-1,-1)
                                self.print_log(type='I',msg='Reading %s<%d:%d> from file to %s.'%(self.ionames[i].upper(),maxbit,minbit,self.name))
                            else:
                                bitrange = range(minbit,maxbit+1,1)
                                self.print_log(type='I',msg='Reading %s<%d:%d> from file to %s.'%(self.ionames[i].upper(),minbit,maxbit,self.name))
                            arr = []
                            for idx in range(maxsamp):
                                word = ''
                                for key in bitrange:
                                    word += outbus[str(key)][idx]
                                arr.append(word)
                            if self.Data is None: 
                                self.Data = np.array(arr).reshape(-1,1)
                            else:
                                self.Data = np.hstack((self.Data,np.array(arr).reshape(-1,1)))
                        infile.close()
                    elif self.parent.model == 'spectre':
                        # Extracting the bus width (TODO: this is copy-pasted a lot -> make into a function)
                        signame = self.ionames[i]
                        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
                        if len(signame) == 1:
                            busstart = 0
                            busstop = 0
                        else:
                            busstart = int(signame[1])
                            busstop = int(signame[2])
                        if busstart > busstop:
                            buswidth = busstart-busstop+1
                        else:
                            buswidth = busstop-busstart+1
                        if self.big_endian:
                            bitrange = range(buswidth)
                        else:
                            bitrange = range(buswidth-1,-1,-1)
                        self.print_log(type='I',msg='Reading bus %s from file to %s.'%(self.ionames[i].upper(),self.name))
                        # Reading each bit of the bus from a file
                        failed = False
                        bitmat = None
                        for j in bitrange:
                            fname = self.file[i].replace('.txt','_%d.txt' % j)
                            # Check if file is empty
                            if os.stat(fname).st_size > 1:
                                arr = genfromtxt(fname,delimiter=', ',skip_header=self.parent.syntaxdict["csvskip"])
                                if len(arr.shape) > 1:
                                    arr = (arr[:,1]>=self.vth).reshape(-1,1).astype(int).astype(str)
                                else:
                                    arr = np.array(['0']).reshape(-1,1)
                                    failed = True
                            else:
                                arr = np.array(['0']).reshape(-1,1)
                                failed = True
                            if bitmat is None:
                                # First bit is read, it becomes the first column of the bit matrix
                                bitmat = arr
                            else:
                                # Following bits get stacked as columns to the left of the previous one
                                bitmat = np.hstack((bitmat,arr))
                        if failed:
                            self.print_log(type='W',msg='Failed reading sample type output vector.')
                        # Bits collected, mashing the rows into binary strings
                        # There's probably a one-liner to do this, I'm lazy
                        arr = []
                        for j in range(len(bitmat[:,0])):
                            arr.append(''.join(bitmat[j,:]))
                        nparr = np.array(arr).reshape(-1,1)
                        # TODO: also this should be a function
                        if self.Data is None: 
                            self.Data = nparr
                        else:
                            if len(self.Data[:,-1]) > len(nparr):
                                # Old max length is bigger -> padding new array
                                nans = np.empty(self.Data[:,-1].shape,dtype='S%s' % buswidth).reshape(-1,1)
                                nans.fill('U' * buswidth)
                                nans = nans.astype(str)
                                nans[:nparr.shape[0],:nparr.shape[1]] = nparr
                                nparr = nans
                            elif len(self.Data[:,-1]) < len(nparr):
                                # Old max length is smaller -> padding old array
                                nans = np.empty(self.Data[:,-1].shape,dtype='S%s' % buswidth).reshape(-1,1)
                                nans.fill('U' * buswidth)
                                nans = nans.astype(str)
                                nans[:self.Data.shape[0],:self.Data.shape[1]] = self.Data
                                self.Data = nans
                            self.Data = np.hstack((self.Data,nparr))
                else:
                    self.print_log(type='F',msg='Couldn\'t read file for input type \'%s\'.'%self.iotype)
            except:
                self.print_log(type='E',msg=traceback.format_exc())
                self.print_log(type='F',msg='Failed while reading files for %s.' % self.name)

    def interp_crossings(self,data,vth,nint,edgetype):
        """ 
        Helper function that is called for 'time' type outputs.
        Interpolates the requested threshold crossings (rising or falling)
        from the 'event' type input signal.
        Returns the time-stamps of the crossing instants in a 1-d vector.
        """
        if edgetype.lower() == 'rising':
            edges = np.flatnonzero((data[:-1,1]<vth) & (data[1:,1]>=vth))+1
        else:
            edges = np.flatnonzero((data[:-1,1]>=vth) & (data[1:,1]<vth))+1
        tcross = np.zeros((len(edges)))
        for i in range(len(edges)):
            try:
                prev = edges[i]-1
                if prev < 0:
                    prev == 0
                xstart = data[prev,0]
                ystart = data[prev,1]
                xstop = data[edges[i],0]
                ystop = data[edges[i],1]
                xinterp = np.linspace(xstart,xstop,nint)
                lerp = np.interp(xinterp,[xstart,xstop],[ystart,ystop])
                if edgetype.lower() == 'rising':
                    tcross[i] = xinterp[np.where(lerp>=vth)[0][0]]
                else:
                    tcross[i] = xinterp[np.where(lerp<=vth)[0][0]]
            except:
                pdb.set_trace()
        # Removing edges happening before self.after
        return tcross[tcross>=self.after]
