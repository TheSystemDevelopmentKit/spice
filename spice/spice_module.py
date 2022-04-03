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
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self, **kwargs):
        # No need to propertize these yet
        self.file=kwargs.get('file','')
        self._name=kwargs.get('name','')
        if not self.file and not self._name:
            self.print_log(type='F', msg='Either name or file must be defined')
    
    @property
    def name(self):
        """String
        
        Entity name."""
        if not self._name:
            self._name=os.path.splitext(os.path.basename(self.file))[0]
        return self._name

    @property
    def DEBUG(self):
        """ This fixes DEBUG prints in spice_iofile, by propagating the DEBUG
        flag of the parent entity.
        """
        return self.parent.DEBUG 

    @property
    def postlayout(self):
        """Boolean
        
        Flag for detected post-layout netlists. This will enable post-layout
        optimizations in the simulator command options. Automatically detected
        from given netlist for Calibre extracted netlists, or when 'dspf'
        attribute is defined.
        """
        if not hasattr(self,'_postlayout'):
            self._postlayout=False
        return self._postlayout
    @postlayout.setter
    def postlayout(self,value):
        self._postlayout=value
    @postlayout.deleter
    def postlayout(self,value):
        self._postlayout=None

    @property
    def subckt(self):
        """String
        
        String containing the contents of the subckt_* -file. This attribute
        parses the source netlist when called, and generates the contents to be
        written to the subckt-file.
        """
        if not hasattr(self,'_subckt'):
            if self.parent.model=='eldo':
                cellnamematch=re.compile(r"\*\*\* Design cell name:",re.IGNORECASE)
                prognamematch=re.compile(r"\* Program",re.IGNORECASE)
                startmatch=re.compile(r"\.SUBCKT",re.IGNORECASE)
                endmatch=re.compile(r"\.ENDS",re.IGNORECASE)
            elif self.parent.model=='spectre':
                cellnamematch=re.compile(r"\/\/ Design cell name:",re.IGNORECASE)
                prognamematch=re.compile(r"\/\/ Program",re.IGNORECASE)
                startmatch=re.compile(r"SUBCKT",re.IGNORECASE)
                endmatch=re.compile(r"ENDS",re.IGNORECASE)
            elif self.parent.model=='ngspice':
                cellnamematch=re.compile(r"\*\*\* Design cell name:",re.IGNORECASE)
                prognamematch=re.compile(r"\* Program",re.IGNORECASE)
                startmatch=re.compile(r"\.SUBCKT",re.IGNORECASE)
                endmatch=re.compile(r"\.ENDS",re.IGNORECASE)
            cellname = ''
            linecount = 0
            self._subckt="%s Subcircuit definitions\n\n" % self.parent.syntaxdict["commentchar"]
            # Extract the module definition
            if os.path.isfile(self._dutfile):
                try:
                    self.print_log(type='D',msg='Parsing source netlist %s' % self._dutfile)
                    with open(self._dutfile) as infile:
                        wholefile=infile.readlines()
                        startfound=False
                        endfound=False
                        for line in wholefile:
                            # First subcircuit not started, finding ADEL written cell name
                            if not startfound and cellnamematch.search(line) != None:
                                words = line.split()
                                cellname = words[-1]
                                self.print_log(type='D',msg='Found top-level cell name "%s".' % cellname)
                                self.origcellname = cellname
                            # First subcircuit not started, finding Calibre xRC written program name
                            if not startfound and prognamematch.search(line) != None:
                                self.print_log(type='D',msg='Post-layout netlist detected (%s).' % (' '.join(line.split()[2:])))
                                # Parsing the post-layout netlist line by line is way too slow
                                # Copying the file and editing it seems better
                                self.postlayout = True
                                # Right now this just ignores everything and overwrites the subcircuit file
                                # TODO: think about this
                                if os.path.isfile(self._subcktfile):
                                    os.remove(self._subcktfile)
                                    shutil.copyfile(self._dutfile,self._subcktfile)
                                else:
                                    shutil.copyfile(self._dutfile,self._subcktfile)
                                for line in fileinput.input(self._subcktfile,inplace=1):
                                    startfound=False
                                    endfound=False
                                    if not startfound and startmatch.search(line) != None:
                                        startfound=True
                                        words = line.split()
                                        if cellname == '':
                                            cellname = words[1].lower()
                                        if words[1].lower() == cellname.lower():
                                            words[1] = self.parent.name.upper()
                                            line = ' '.join(words) + "\n"
                                    self._subckt += line 
                                    sys.stdout.write(line)
                                if cellname != self.parent.name:
                                    self.print_log(type='D',msg='Renaming design cell %s to %s.' % (cellname,self.parent.name))
                                # Notice the return here
                                return self._subckt
                            # First subcircuit not started, starts on this line though
                            if not startfound and startmatch.search(line) != None:
                                startfound=True
                                words = line.split()
                                # Either it's a postlayout netlist, or the cell name was not defined
                                # in the header -> assuming first subcircuit is top-level circuit
                                if cellname == '':
                                    cellname = words[1].lower()
                                    self.print_log(type='D',msg='Renaming design cell %s to %s.' % (cellname,self.parent.name))
                                if words[1].lower() == cellname.lower():
                                    self._subckt+="\n%s Subcircuit definition for %s module\n" % (self.parent.syntaxdict["commentchar"],self.parent.name)
                                    words[1] = self.parent.name.upper()
                                    if cellname != self.parent.name:
                                        self.print_log(type='D',msg='Renaming design cell "%s" to "%s".' % (cellname,self.parent.name))
                                    line = ' '.join(words) + "\n"
                                    linecount += 1
                            # Inside the subcircuit clause -> copy all lines except comments
                            if startfound:
                                words = line.split()
                                if len(words) > 0 and words[0] != self.parent.syntaxdict["commentchar"]:
                                    if words[0] == 'subckts': #todo: figure out what this spectre line does
                                        startfound=False
                                    else:
                                        # Top-level subcircuit ends here, renaming old name to entity name
                                        if len(words) > 0 and words[0].lower() == 'ends' \
                                                and words[1].lower() == cellname.lower():
                                            words[-1] = self.parent.name.upper()
                                            line =  ' '.join(words) + '\n'
                                        self._subckt=self._subckt+line
                                        linecount += 1
                            # Calibre places an include statement above the first subcircuit -> grab that
                            if len(self.parent.dspf) == 0 and self.postlayout and not startfound:
                                words = line.split()
                                if words[0].lower() == self.parent.syntaxdict["include"]:
                                    self._subckt=self._subckt+line
                                    linecount += 1
                            # End of subcircuit found
                            if startfound and endmatch.search(line) != None:
                                startfound=False
                    self.print_log(type='D',msg='Source netlist parsing done (%d lines).' % linecount)
                except:
                    self.print_log(type='E',msg='Something went wrong while parsing %s.' % self._dutfile)
                    self.print_log(type='E',msg=traceback.format_exc())
            else:
                self.print_log(type='W',msg='File %s not found.' % self._dutfile)
        return self._subckt
    @subckt.setter
    def subckt(self,value):
        self._subckt=value
    @subckt.deleter
    def subckt(self,value):
        self._subckt=None

    def subinst_constructor(self,**kwargs):
        """ Method that parses the subcircuit definition and 
        constructs a subcircuit instance out of it.

        Parameters
        ----------
        **kwargs:  
            subckt : string

        """
        subckt=kwargs.get('subckt')
        startmatch=re.compile(r"%s %s " %(self.parent.syntaxdict["subckt"], self.parent.name.upper())
                ,re.IGNORECASE)

        if len(subckt) <= 3:
            self.print_log(type='W',msg='No subcircuit found.')
            self._subinst = "%s Empty subcircuit\n" % (self.parent.syntaxdict["commentchar"])

        else:
            self._subinst = "%s Subcircuit instance\n" % (self.parent.syntaxdict["commentchar"])
            startfound = False
            endfound = False
            lastline = False
            for line in subckt:
                if self.parent.model == 'eldo':
                    if startmatch.search(line) != None:
                        startfound = True
                    elif startfound and len(line) > 0:
                        if line[0] != '+':
                            endfound = True
                            startfound = False
                elif self.parent.model == 'spectre':
                    if startmatch.search(line) != None:
                        startfound = True
                    if startfound and len(line) > 0:
                        if lastline:
                            endfound = True
                            startfound = False
                        if not line[-1] == '\\':
                            lastline = True
                # For consistency, even though identical to eldo
                elif self.parent.model == 'ngspice':
                    if startmatch.search(line) != None:
                        startfound = True
                    elif startfound and len(line) > 0:
                        if line[0] != '+':
                            endfound = True
                            startfound = False
                if startfound and not endfound:
                    words = line.split(" ")
                    if words[0].lower() == self.parent.syntaxdict["subckt"]:
                        if self.parent.model == 'eldo':
                            words[0] = "X%s%s" % (self.parent.name.upper(),'')  
                        elif self.parent.model == 'spectre':
                            words[0] = "X%s%s" % (self.parent.name.upper(), ' (')
                        elif self.parent.model == 'ngspice':
                            words[0] = "X%s%s" % (self.parent.name.upper(),'')  
                        words.pop(1)
                        line = ' '.join(words)
                    self._subinst += line + "%s\n" % ('\\' if lastline else '')
            if self.parent.model == 'eldo':
                self._subinst += ('+')  + self.parent.name.upper()
            elif self.parent.model == 'spectre':
                self._subinst += (') ' )  + self.parent.name.upper()
            elif self.parent.model == 'ngspice':
                self._subinst += ('+')  + self.parent.name.upper()
        

    @property
    def subinst(self):
        """String
        
        String containing the subcircuit instance to be placed in the
        testbench. The instance is parsed from the previously generated
        subckt_* -file.
        """
        try:
            if not hasattr(self,'_subinst'):
                subckt = self.subckt.split('\n')

                if not self.postlayout:
                    if len(subckt) <= 3:
                            self.print_log(type='W',msg='No subcircuit found.')
                            self._subinst = "%s Empty subcircuit\n" % (self.parent.syntaxdict["commentchar"])
                    else:
                        self.subinst_constructor(subckt=subckt)
                else:
                    # This part is supposed to be the constructor copy-pasted, 
                    # only difference should be that its read from a file
                    # However it is not.
                    # TODO: needs obvious refactoring
                    if self.parent.model=='eldo':
                        startmatch=re.compile(r"\.SUBCKT %s " % self.parent.name.upper(),re.IGNORECASE)
                    elif self.parent.model=='spectre':
                        startmatch=re.compile(r"\SUBCKT %s " % self.parent.name.upper(),re.IGNORECASE)
                    elif self.parent.model=='ngspice':
                        startmatch=re.compile(r"\.SUBCKT %s " % self.parent.name.upper(),re.IGNORECASE)
                    self._subinst = "%s Subcircuit instance\n" % (self.parent.syntaxdict["commentchar"])
                    startfound = False
                    endfound = False
                    lastline = False
                    with open(self._subcktfile) as infile:
                        subckt=infile.readlines()

                        for line in subckt:
                            if self.parent.model == 'spectre':
                                line = line.replace('\n','')
                            if startmatch.search(line) != None:
                                startfound = True
                            if startfound and len(line) > 0:
                                if self.parent.model == 'eldo' and line[0] != '+':
                                    endfound = True
                                    startfound = False
                                elif self.parent.model == 'spectre':
                                    if lastline:
                                        endfound = True
                                        startfound = False
                                    if not line[-1] == '\\':
                                        lastline = True
                            if startfound and not endfound:
                                words = line.split(" ")
                                if words[0].lower() == self.parent.syntaxdict["subckt"]:
                                    words[0] = "X%s" % (self.parent.name.upper())
                                    words.pop(1)
                                    line = ' '.join(words)
                                self._subinst += line + "%s\n" % ('\\' if lastline else '')
                        self._subinst += '+' if self.parent.model == 'eldo' else ''  + self.parent.name.upper()
            return self._subinst
        except:
            self.print_log(type='E',msg='Something went wrong while generating subcircuit instance.')
            self.print_log(type='E',msg=traceback.format_exc())
            pdb.set_trace()
    @subinst.setter
    def subinst(self,value):
        self._subinst=value
    @subinst.deleter
    def subinst(self,value):
        self._subinst=None

if __name__=="__main__":
    pass
