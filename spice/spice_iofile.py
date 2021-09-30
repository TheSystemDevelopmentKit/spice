"""
=============
Spice IO-file
=============

Provides spice file IO related attributes and methods 
for TheSDK spice.

Initially written by Okko Järvinen, 2020

"""
import os
import sys
import subprocess
import multiprocessing
import pdb
from abc import * 
from thesdk import *
from thesdk.iofile import iofile
import numpy as np
import pandas as pd
from numpy import genfromtxt
import traceback
from bitstring import BitArray

class spice_iofile(iofile):
    """
    Class to provide file IO for spice simulations. When created, 
    adds a spice_iofile object to the parents iofile_bundle property.
    Accessible as iofile_bundle.Members['name'].

    Parameters
    ----------
    parent : object 
        The parent object initializing the spice_iofile instance. Default None
    name : str
        Name of the IO.
    dir : 'in' or 'out'
        Direction of the IO.
    iotype : 'event', 'sample' or 'time'
        Type of the IO signal. Event type signals are time-value pairs (analog
        signal), whereas sample type signals are sampled by a clock signal
        (digital bus). Sample type signals can be used for discrete time &
        continuous amplitude outputs (sampled voltage for example), by setting
        iotype='sample' and ioformat='volt'. Time type signals return a vector
        of timestamps corresponding to threshold crossings.
    ioformat : 'dec', 'bin' or 'volt'
        Formatting of the sampled signals. Digital output buses are formatted
        to unsigned integers when ioformat = 'dec'. For 'bin', the digital
        output bus is returned as a string containing ones and zeros. When
        ioformat = 'volt', the output signal is sampled at the clock and the
        floating point value is returned. Voltage sampling is only supported
        for non-bus signals.
    sourcetype : 'V', 'I' or 'ISUB'
        Type of the source associated to a file. Default 'V'.
    datatype : str
        Inherited from the parent. If complex, the ioname is handled as a
        complex signal. Currently implemented only for writing the ouputs in
        testbenches and reading them in. 
    trigger : str or list<str>
        Name of the clock signal node in the Spice netlist. If a single string
        is given, the same clock signal is used for all bits/buses. If a list
        is given, and the length matches ionames list length, each ioname will
        be assigned its own clock. Applies only to sample type outputs.
    vth : float
        Threshold voltage of the trigger signal and the bit rounding. Applies
        only to sample type outputs.
    edgetype : 'rising', 'falling' or 'both'
        Type of triggering edge. When time type signal is used, the edgetype
        values can define the extraction type as 'risetime' or 'falltime'
        additionally. Default 'rising'.
    after : float
        Initial delay added to the input signal (sample) or time extraction
        (time). Useful for ignoring inital settling, for example. Applies only
        to sample and time outputs. Default 0.
    big_endian : bool
        Flag to read the extracted bus as big-endian. Applies only to sample
        type outputs. Default False.
    rs : float
        Sample rate of the sample type input. Default None.
    vhi : float
        High bit value of sample type input. Default 1.0.
    vlo : float
        Low bit value of sample type input. Default 0.
    tfall : float
        Falltime of sample type input. Default 5e-12.
    trise : float
        Risetime of sample type input. Default 5e-12.

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

        _=spice_iofile(self,name='dout',dir='out',iotype='sample',sourcetype='V',ioformat='bin',
                       ionames='DOUT<7:0>',edgetype='falling',vth=self.vdd/2,trigger='CLK')

    Defining a discrete time & continuous amplitude output signal triggered
    with a rising edge of the analog clock. The iofile returns a 2D-vector
    similar to 'event' type signals::

        _=spice_iofile(self,name='sampled_input',dir='out',iotype='sample',sourcetype='V',ioformat='volt',
                       ionames='INP',edgetype='rising',vth=self.vdd/2,trigger='CLK')

    Defining digital input signal with decimal format. The input vector is a
    list of integers, which get converted to binary bus of 4-bits (inferred
    from 'CTRL<3:0>'). The values are changed at 1 MHz interval in this
    example.::

        _=spice_iofile(self,name='ctrl',dir='in',iotype='sample',ionames='CTRL<3:0>',rs=1e6,
                       vhi=self.vdd,trise=5e-12,tfall=5e-12,ioformat='dec')
        
    """
    def __init__(self,parent=None,**kwargs):
        if parent==None:
            self.print_log(type='F', msg="Parent of spice input file not given")
        try:  
            super(spice_iofile,self).__init__(parent=parent,**kwargs)
            self.paramname=kwargs.get('param','-g g_file_')
            self.ioformat=kwargs.get('ioformat','dec')
            self.trigger=kwargs.get('trigger','')
            self.vth=kwargs.get('vth',0.5)
            self.edgetype=kwargs.get('edgetype','rising')
            self.after=kwargs.get('after',0)
            self.big_endian=kwargs.get('big_endian',False)
            self.rs=kwargs.get('rs',None)
            self.vhi=kwargs.get('vhi',1.0)
            self.vlo=kwargs.get('vlo',0)
            self.tfall=kwargs.get('tfall',5e-12)
            self.trise=kwargs.get('trise',5e-12)
            self.sourcetype=kwargs.get('sourcetype','V')
        except:
            self.print_log(type='F', msg="spice IO file definition failed.")

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
            filepath = self.parent.spicesimpath+'/'
            # For now, all outputs are event type stored in a common file
            if self.dir == 'out':
                filename = 'tb_%s.print' % (self.parent.name)
            else:
                filename = ( '%s_%s_%s_%s.txt' 
                    % ( self.parent.runname,self.dir,ioname.replace('<','').replace('>','').replace('.','_'),
                        self.iotype))
            if self.parent.model == 'ngspice' and self.dir == 'in':
                # For some reason Ngspice requires lowercase names
                filename = filename.lower()
            filename = filepath + filename    
            self._file.append(filename)
        # Keep unique filenames only for event-type outputs to keep load times at minimum
        if self.iotype=='event' and self.dir=='out':
            self._file=list(set(self._file))
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
                    self.print_log(type='I',msg='Writing event input %s' % self.file[i])
            except:
                    self.print_log(type='E',msg=traceback.format_exc())
                    self.print_log(type='E',msg='Failed writing %s' % self.file[i])
        elif self.iotype == 'sample':
            try:
                for i in range(len(self.file)):
                    self.print_log(type='I',msg='Writing sample input %s' % self.file[i])
                    if not isinstance(self.Data,int):
                        # Input is a vector
                        vec = self.Data[:,i]
                    else:
                        # Input is a scalar value
                        vec = [self.Data]
                    # Extracting the bus width
                    signame = self.ionames[i]
                    busstart,busstop,buswidth,busrange = self.parent.get_buswidth(signame)
                    signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')
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
                self.print_log(type='E',msg='Failed while writing files for %s' % self.file[i])
        else:
            pass

    def parse_io_from_file(self,filepath,start,stop,dtype,label,queue):
        """ Parse specific lines from a spectre print file.

        This is wrapped to a function to allow parallelism.
        """
        try:
            arr=np.genfromtxt(filepath,dtype=dtype,skip_header=start,skip_footer=stop,encoding='utf-8')
            # TODO: This is not enabled by setting self.DEBUG = True for some
            # reason.. Should this class inherit thesdk?
            self.print_log(type='D',msg='Reading event output %s' % label)
            queue.put((label,arr))
        except:
            self.print_log(type='E',msg='Failed reading event output %s' % label)
            queue.put((label,None))

    # Overloaded read from thesdk.iofile
    def read(self,**kwargs):
        """
        Function to read files associated with this spice_iofile.
        """
        if self.iotype=='event':
            file=self.file[0] # File is the same for all event type outputs
            label_match=re.compile(r'\((.*)\)')
            if self.parent.model in ['spectre','ngspice']:
                lines=subprocess.check_output('grep -n \"time\|freq\" %s' % file, shell=True).decode('utf-8')
                lines=lines.split('\n') 
                linenumbers=[]
                labels=[]
                for line in lines:
                    parts=line.split(':')
                    if len(parts) > 1: # Line should now contain linenumber in first element, ioname in second
                        line = 0
                        try:
                            line=int(parts[0])
                            linenumbers.append(line)
                        except ValueError:
                            self.print_log(type='W', msg='Couldn\'t decode linenumber from file %s' %  file)
                        label=label_match.search(parts[1])
                        if label:
                            labels.append(label.group(1)) # Capture inner group (== ioname)
                        else:
                            self.print_log(type='W', msg='Couldn\'t find IO on line %d from file %s' %  (line,file))
                if len(labels) == len(linenumbers):
                    numlines = int(subprocess.check_output("wc -l %s | awk '{print $1}'" % file,shell=True).decode('utf-8'))
                    procs = []
                    queues = []
                    for k in range(len(linenumbers)):
                        start=linenumbers[k] # Indexing starts from zero
                        if k == len(linenumbers)-1:
                            stop=1
                        else:
                            stop=numlines-(linenumbers[k+1]-6) # Previous data column ends 5 rows before start of next one
                        dtype=self.datatype if self.datatype=='complex' else 'float' # Default is int for thesdk_spicefile, let's infer from data
                        queue = multiprocessing.Queue()
                        queues.append(queue)
                        proc = multiprocessing.Process(target=self.parse_io_from_file,args=(file,start,stop,dtype,labels[k],queue))
                        procs.append(proc)
                        proc.start() 
                    for i,p in enumerate(procs):
                        try:
                            ret = queues[i].get()
                            self.parent.iofile_eventdict[ret[0].upper()]=ret[1]
                            p.join()
                        except KeyError:
                            self.print_log(type='W', msg='Failed reading %s' % (ret[0]))
                else:
                    self.print_log(type='W', msg='Couldn\'t read IOs from file %s. Missing ioname?' % file)
            elif self.parent.model == 'eldo':
                # Parse signal headers
                with open(file,'r') as f:
                    for line in f.readlines():
                        if line.startswith('# TIME') or line.startswith('# FREQ'):
                            header = line.replace('# ','').replace('\n','').split(' ')
                            break
                arr = np.genfromtxt(file)
                if len(header) != len(arr[0,:]):
                    self.print_log(type='E', msg='Signal name and array column mismatch while reading event outputs.')
                for col_idx,sname in enumerate(header[1:]):
                    label=label_match.search(sname)
                    if label:
                        label = label.group(1)
                        # Add to the event dictionary
                        self.parent.iofile_eventdict[label.upper()]=np.hstack((arr[:,0].reshape(-1,1),arr[:,col_idx+1].reshape(-1,1))).reshape(-1,2)
                    else:
                        self.print_log(type='W', msg='Label format mismatch with \'%s\'.' %  (label))
        else:
            for i in range(len(self.file)):
                try:
                    if self.iotype=='vsample':
                        self.print_log(type='O',msg='IO type \'vsample\' is obsolete. Please use type \'sample\' and set ioformat=\'volt\'.')
                        self.print_log(type='F',msg='Please do it now :)')
                    elif self.iotype=='time':
                        # TODO: Make sure all 'event' iofiles are parsed before 'time' iofiles
                        if self.ionames[i].upper() in self.parent.iofile_eventdict:
                            arr = self.parent.iofile_eventdict[self.ionames[i].upper()]
                        else:
                            self.print_log(type='E',msg='No event data found for %s while parsing time signal.' % self.ionames[i])
                        # This should work for both spectre and eldo now
                        if self.edgetype.lower() == 'both':
                            trise = self.interp_crossings(arr,self.vth,256,'rising')
                            tfall = self.interp_crossings(arr,self.vth,256,'falling')
                            tcross = np.sort(np.vstack((trise.reshape(-1,1),tfall.reshape(-1,1))),0)
                        else:
                            tcross = self.interp_crossings(arr,self.vth,256,self.edgetype)
                        nparr = np.array(tcross).reshape(-1,1)
                        # Adding nparr to self.Data
                        self.append_to_data(arr=nparr,bits=False)
                    elif self.iotype=='sample':
                        # Extracting the bus width
                        signame = self.ionames[i]
                        busstart,busstop,buswidth,busrange = self.parent.get_buswidth(signame)
                        signame = signame.replace('<',' ').replace('>',' ').replace('[',' ').replace(']',' ').replace(':',' ').split(' ')

                        # Find trigger signal threshold crossings
                        if isinstance(self.trigger,list):
                            if len(self.trigger) == len(self.ionames):
                                trig = self.trigger[i]
                            else:
                                trig = self.trigger[0]
                        else:
                            trig = self.trigger
                        if trig.upper() not in self.parent.iofile_eventdict:
                            self.print_log(type='E',msg='Event data not found for trigger signal %s' % trig)
                        else:
                            trig_event = self.parent.iofile_eventdict[trig]
                            tsamp = self.interp_crossings(trig_event,self.vth,256,self.edgetype)

                        # Processing each bit in the bus
                        self.print_log(type='I',msg='Sampling %s with %s (%s).'%(self.ionames[i],trig,self.edgetype))
                        failed = False
                        bitmat = None
                        for j in busrange:
                            # Get event data for the bit voltage
                            if buswidth == 1 and '<' not in self.ionames[i]:
                                bitname = signame[0]
                            else:
                                bitname = '%s<%d>' % (signame[0],j)
                            if bitname.upper() not in self.parent.iofile_eventdict:
                                event = np.array(['0']).reshape(-1,1)
                                failed = True
                            else:
                                event = self.parent.iofile_eventdict[bitname.upper()]
                            # Sample the signal
                            arr = self.sample_signal(event,tsamp)
                            # Binary or decimal io format, rounding to bits
                            if self.ioformat != 'volt':
                                if len(arr.shape) > 1:
                                    arr = (arr[:,1]>=self.vth).reshape(-1,1).astype(int).astype(str)
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
                        if self.ioformat == 'volt':
                            nparr = bitmat
                        else:
                            # Merging bits to buses
                            arr = []
                            for j in range(len(bitmat[:,0])):
                                arr.append(''.join(bitmat[j,:]))
                            nparr = np.array(arr).reshape(-1,1)
                            # Convert binary strings to decimals
                            if self.ioformat == 'dec':
                                b2i = np.vectorize(self._bin2int)
                                # For now only little-endian unsigned
                                nparr = b2i(nparr)
                        # Adding nparr to self.Data
                        self.append_to_data(arr=nparr,bits=True,buswidth=buswidth)
                    else:
                        self.print_log(type='F',msg='Couldn\'t read file for input type \'%s\'.'%self.iotype)
                except:
                    self.print_log(type='E',msg=traceback.format_exc())
                    self.print_log(type='F',msg='Failed while reading files for %s.' % self.name)

    def interp_crossings(self,data,vth,nint,edgetype):
        """ Helper method called for 'time' and 'sample' type outputs.

        Interpolates the requested threshold crossings (rising or falling) from
        the 'event' type input signal. Returns the time-stamps of the crossing
        instants in a 1D-vector.

        Parameters
        ----------
        data : ndarray
            Input data array. Expected an 'event' type 2D-vector where first
            column is time and second is voltage.
        vth : float
            Threshold voltage.
        nint : int
            Interpolation factor. The two closest points on each side of a
            threshold crossing are used for linear interpolation endpoints,
            where nint points are added to find as close x-value of the
            threshold crossing as possible. 
        edgetype : str
            Direction of the crossing: 'rising', 'falling' or 'both'.

        Returns
        -------
        ndarray
            1D-vector with time-stamps of interpolated threshold crossings.

        """
        if edgetype.lower() == 'rising':
            edges = np.flatnonzero((data[:-1,1]<vth) & (data[1:,1]>=vth))+1
        else:
            edges = np.flatnonzero((data[:-1,1]>=vth) & (data[1:,1]<vth))+1
        tcross = np.zeros((len(edges)))
        # Potentially slow (TODO?)
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

    def sample_signal(self,signal,trigger,nint=1):
        """ Helper method called for 'sample' type outputs.

        Finds the signal y-values at time instants defined by the clock signal
        (trigger).

        Parameters
        ----------
        data : ndarray
            Input data array. Expected an 'event' type 2D-vector where first
            column is time and second is voltage.
        vth : float
            Threshold voltage.
        nint : int
            Interpolation factor. The two closest points on each side of a
            threshold crossing are used for linear interpolation endpoints,
            where nint points are added to find as close x-value of the
            threshold crossing as possible. 
        edgetype : str
            Direction of the crossing: 'rising', 'falling' or 'both'.

        Returns
        -------
        ndarray
            1D-vector with time-stamps of interpolated threshold crossings.

        """
        sampled = np.ones((len(trigger),2))*np.nan
        for i in range(len(trigger)):
            tsamp = trigger[i]
            closest_idx = np.argmin(np.abs(signal[:,0]-tsamp))
            sampled[i,0] = signal[closest_idx,0]
            sampled[i,1] = signal[closest_idx,1]
        return sampled

    def _bin2int(self,binary,big_endian=False,signed=False):
        ''' Helper method to convert binary string to integer.
        '''
        if big_endian:
            if signed:
                return BitArray(bin=binary).int
            else:
                return int(binary,2)
        else:
            if signed:
                return BitArray(bin=binary[::-1]).int
            else:
                return int(binary[::-1],2)

    def append_to_data(self,arr=None,bits=False,buswidth=None):
        ''' Helper method to append array to self.Data.
        
        The array(s) are padded with np.nan when bits=False, and 'UUUU' when
        bits=True. This is called automatically for time and sample type IOs.
        '''
        filler = 'U'*buswidth if bits else np.nan
        dtype = 'S%s'%buswidth if bits else np.double
        if self.Data is None: 
            self.Data = arr
        else:
            if len(self.Data[:,-1]) > len(arr):
                # Old max length is bigger -> padding new array
                padded = np.empty(self.Data[:,-1].shape,dtype=dtype).reshape(-1,1)
                padded.fill(filler)
                if bits: 
                    padded = padded.astype(str)
                padded[:arr.shape[0],:arr.shape[1]] = arr
                arr = padded
            elif len(self.Data[:,-1]) < len(arr):
                # Old max length is smaller -> padding old array
                padded = np.empty((arr.shape[0],self.Data.shape[1]),dtype=dtype)
                padded.fill(filler)
                if bits: 
                    padded = padded.astype(str)
                padded[:self.Data.shape[0],:self.Data.shape[1]] = self.Data
                self.Data = padded
            self.Data = np.hstack((self.Data,arr))
