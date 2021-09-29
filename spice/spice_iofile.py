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
        
    Parameters
    -----------
    parent : object 
        The parent object initializing the 
        spice_iofile instance. Default None
    
    **kwargs :  
            name (str)
                Name of the IO.
            dir (str)
                Direction of the IO: 'in'/'out'.
            iotype (str)
                Type of the IO signal: 'event'/'sample'/'time'.  Event type
                signals are time-value pairs (analog signal), while sample type
                signals are sampled by a clock signal (digital bus).  Sample
                type signals can be used for discrete time & continuous
                amplitude outputs (sampled voltage for example), by setting
                iotype='sample' and ioformat='volt'. Time type signals return
                a vector of timestamps corresponding to threshold crossings.
            ioformat {'dec','bin','volt'}
                Formatting of the sampled signals. Digital output buses are
                formatted to unsigned integers when ioformat = 'dec'. For
                'bin', the digital output bus is returned as a string
                containing ones and zeros. When ioformat = 'volt', the output
                signal is sampled at the clock and the floating point value is
                returned. Voltage sampling is only supported for non-bus
                signals.
                Default 'dec'.
            datatype (str)
                Inherited from the parent.
                If complex, the ioname is handled as a complex signal.
                Currently implemented only for writing the ouputs in testbenched and reading them in. 
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
            sourcetype (str)
                Type of the source associated to a file.
                V | I | ISUB (for spectre, event type)
                Default 'V'
    """
    def __init__(self,parent=None,**kwargs):
        if parent==None:
            self.print_log(type='F', msg="Parent of spice input file not given")
        try:  
            super(spice_iofile,self).__init__(parent=parent,**kwargs)
            self.paramname=kwargs.get('param','-g g_file_')
            self._ioformat=kwargs.get('ioformat','dec')
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
            self._sourcetype=kwargs.get('sourcetype','V')
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
        """ Helper function called for 'time' and 'sample' type outputs.

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
        """ Helper function called for 'sample' type outputs.

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
        ''' Function to convert binary string to integer.
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
