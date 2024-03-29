"""
============
Spice Module
============

Class for Spice netlist parsing.

"""
import os
import pdb
import shutil
import fileinput
import sys
from thesdk import *
from spice import *
from copy import deepcopy
import traceback

class spice_module(thesdk):
    """
    This class parses source netlist for subcircuits and handles the generation
    of a separate pruned subckt_* -file. This class is internally utilized by
    the spice_testbench module.

    """

    def __init__(self, **kwargs):
        # No need to propertize these yet
        self._file=kwargs.get('file','')
        self._name=kwargs.get('name','')
        self.parent=kwargs.get('parent') # There should be no need for parent in this module
        if not self.file and not self._name:
            self.print_log(type='F', msg='Either name or file must be defined')

    @property
    def file(self):
        """ Filepath to the entity's spice netlist source file 
        (i.e. './spice/entityname.scs').  
        
        :type: str
        
        """
        if not hasattr(self,'_file'):
            self._file=None
        return self._file
    @file.setter
    def file(self,value):
            self._file=value
    
    @property
    def name(self):
        """Entity name
        
        :type: str

        """
        if not self._name:
            self._name=os.path.splitext(os.path.basename(self.file))[0]
        return self._name

    @property
    def custom_subckt_name(self):
        """Custom name of the subcircuit to look from from the netlist file during parsing for 
        'subckt' property. Enables using compatible (in term sof IOs paremeters) netlists defined 
        for designs of different name.

        :type: str
 
        Example:
            Most common use case of module is a dut in a testbench. There you 
            can set this parameter before execution as::

                self.spice_tb.dut.custom_subckt_name = 'some_name'
                self.run_spice()

        """
        if not hasattr(self,'_custom_subckt_name'):
            self._custom_subckt_name = None
        return self._custom_subckt_name

    @custom_subckt_name.setter
    def custom_subckt_name(self,value):
        self._custom_subckt_name = value

    @property
    def subckt(self):
        """The contents of the subcircuit definition file of the entity.
        Extract the definitions form the source netlist. The source netlist when accessed. 
        Can be written to the subckt_file with export_subckt method. 

        :type: str

        """
        if not hasattr(self,'_subckt'):
            self._subckt="%s Subcircuit definitions\n\n" % self.parent.spice_simulator.commentchar
            # Extract the module definition
            if os.path.isfile(self.file):
                try:
                    self.print_log(type='D',msg='Parsing source netlist %s' % self.file)
                    if self.custom_subckt_name:
                        #Replace subcircuit_custom_name with parent.name
                        self._subckt += subprocess.check_output(
                                'sed -n \'/\.*[sS][uU][bB][cC][kK][tT]\s\s*/,/\.*[eE][nN][dD][sS]/p\' %s | sed \'s/%s/%s/g\'' 
                                % (self.file,self.custom_subckt_name,self.parent.name), shell=True).decode('utf-8')
                    else:
                        self._subckt += subprocess.check_output(
                                'sed -n \'/\.*[sS][uU][bB][cC][kK][tT]\s\s*/,/\.*[eE][nN][dD][sS]/p\' %s' 
                                % self.file, shell=True).decode('utf-8')
                except:
                    self.print_log(type='E',msg='Something went wrong while parsing %s.' % self.file)
                    self.print_log(type='E',msg=traceback.format_exc())
            else:
                self.print_log(type='W',msg='File %s not found.' % self.file)
        return self._subckt
    @subckt.setter
    def subckt(self,value):
        self._subckt=value
    @subckt.deleter
    def subckt(self,value):
        self._subckt=None

    @property
    def instance(self):
        """The subcircuit instance to be placed in the testbench. Parsed from
        the subckt property

        :type: str
        
        """
        try:
            if not hasattr(self,'_instance'):
                subckt = self.subckt.split('\n')
                startmatch=re.compile(r"%s %s " %(self.parent.spice_simulator.subckt, self.parent.name)
                        ,re.IGNORECASE)

                if len(subckt) <= 3:
                    self.print_log(type='W',msg='No subcircuit found.')
                    self._instance = "%s Empty subcircuit\n" % (self.parent.spice_simulator.commentchar)

                else:
                    self._instance = "%s Subcircuit instance\n" % (self.parent.spice_simulator.commentchar)
                    startfound = False
                    endfound = False
                    lastline = False
                    for line in subckt:
                        if startmatch.search(line) != None:
                            startfound = True
                            # For spectre we need to process the statline as potential endline
                            if self.parent.model == 'spectre':
                                if startfound and len(line) > 0:
                                    if lastline:
                                        endfound = True
                                        startfound = False
                                    if not line[-1] == '\\':
                                        lastline = True
                        elif startfound and len(line) > 0:
                            if self.parent.model == 'eldo':
                                if line[0] != '+':
                                    endfound = True
                                    startfound = False
                            elif self.parent.model == 'spectre':
                                if lastline:
                                    endfound = True
                                    startfound = False
                                if not line[-1] == '\\':
                                    lastline = True
                            # For consistency, even though identical to eldo
                            elif self.parent.model == 'ngspice':
                                if line[0] != '+':
                                    endfound = True
                                    startfound = False
                        if startfound and not endfound:
                            words = line.split(" ")
                            if words[0].lower() == self.parent.spice_simulator.subckt:
                                if self.parent.model == 'eldo':
                                    words[0] = "X%s%s" % (self.parent.name,'')  
                                elif self.parent.model == 'spectre':
                                    words[0] = "X%s%s" % (self.parent.name, ' (')
                                elif self.parent.model == 'ngspice':
                                    words[0] = "X%s%s" % (self.parent.name,'')  
                                words.pop(1)
                                line = ' '.join(words)
                            self._instance += line + "%s\n" % (' \\' if lastline else '')
                    if self.parent.model == 'eldo':
                        self._instance += ('+')  + self.parent.name
                    elif self.parent.model == 'spectre':
                        self._instance += (') ' )  + self.parent.name
                    elif self.parent.model == 'ngspice':
                        self._instance += ('+')  + self.parent.name
                return self._instance
        except:
            self.print_log(type='E',msg='Something went wrong while generating subcircuit instance.')
            self.print_log(type='E',msg=traceback.format_exc())
    @instance.setter
    def instance(self,value):
        self._instance=value
    @instance.deleter
    def instance(self,value):
        self._instance=None

    def export_subckts(self,**kwargs):
        """
        Internally called function to write the parsed subcircuit definitions
        to a file.

        Parameters
        ----------
        file : str
            Path to file where to write.
        force : Bool, False
            Force writing
        """
        file = kwargs.get('file')
        force = kwargs.get('force', False)
        if not os.path.isfile(file):
            self.print_log(type='D',msg='Exporting spice subcircuit to %s' %(file))
            with open(file, "w") as module_file:
                module_file.write(self.subckt)
        elif os.path.isfile(file) and not force:
            self.print_log(type='F', msg=('Export target file %s exists.\n Force overwrite with force=True.' %(file)))
        elif force:
            self.print_log(type='I',msg='Forcing overwrite of spice subcircuit to %s.' %(file))
            with open(file, "w") as module_file:
                module_file.write(self.subckt)

if __name__=="__main__":
    pass
