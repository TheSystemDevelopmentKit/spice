# Written by Marko Kosunen 20190109
# marko.kosunen@aalto.fi
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
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self, **kwargs):
        # No need to propertize these yet
        self.file=kwargs.get('file','')
        self._name=kwargs.get('name','')
        self._instname=kwargs.get('instname',self.name)
        if not self.file and not self._name:
            self.print_log(type='F', msg='Either name or file must be defined')
    
    
    @property
    def name(self):
        if not self._name:
            self._name=os.path.splitext(os.path.basename(self.file))[0]
        return self._name

    @property
    def instname(self):
        if not hasattr(self,'_instname'):
            self._instname=self.name+'_DUT'
        return self._instname
    @instname.setter
    def instname(self,value):
            self._instname=value

    @property
    def postlayout(self):
        if not hasattr(self,'_postlayout'):
            self._postlayout=False
        return self._postlayout
    @postlayout.setter
    def postlayout(self,value):
        self._postlayout=value
    @postlayout.deleter
    def postlayout(self,value):
        self._postlayout=None

    # Parsing the subcircuit definition from input netlist
    @property
    def subckt(self):
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
            cellname = ''
            linecount = 0
            self._subckt="%s Subcircuit definitions\n\n" % self.parent.syntaxdict["commentchar"]
            # Extract the module definition
            if os.path.isfile(self._dutfile):
                try:
                    with open(self._dutfile) as infile:
                        wholefile=infile.readlines()
                        startfound=False
                        endfound=False
                        for line in wholefile:
                            # First subcircuit not started, finding ADEL written cell name
                            if not startfound and cellnamematch.search(line) != None:
                                words = line.split()
                                cellname = words[-1]
                                self.print_log(type='I',msg='Found cell-name definition ("%s").' % cellname)
                            # First subcircuit not started, finding Calibre xRC written program name
                            if not startfound and prognamematch.search(line) != None:
                                self.print_log(type='I',msg='Post-layout netlist detected (%s).' % (' '.join(line.split()[2:])))
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
                                    sys.stdout.write(line)
                                self.print_log(type='I',msg='Renaming design cell %s to %s.' % (cellname,self.parent.name))
                                self._subckt = ''
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
                                    self.print_log(type='I',msg='Renaming design cell %s to %s.' % (cellname,self.parent.name))
                                if words[1].lower() == cellname.lower():
                                    self._subckt+="\n%s Subcircuit definition for %s module\n" % (self.parent.syntaxdict["commentchar"],self.parent.name)
                                    words[1] = self.parent.name.upper()
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
                            if self.postlayout and not startfound:
                                words = line.split()
                                if words[0].lower() == self.parent.syntaxdict["include"]:
                                    self._subckt=self._subckt+line
                                    linecount += 1
                            # End of subcircuit found
                            if startfound and endmatch.search(line) != None:
                                startfound=False
                    self.print_log(type='I',msg='Source netlist parsing done (%d lines).' % linecount)
                except:
                    self.print_log(type='E',msg='Something went wrong while parsing %s.' % self._dutfile)
                    self.print_log(type='I',msg=traceback.format_exc())
            else:
                self.print_log(type='W',msg='File %s not found.' % self._dutfile)
        return self._subckt
    @subckt.setter
    def subckt(self,value):
        self._subckt=value
    @subckt.deleter
    def subckt(self,value):
        self._subckt=None

    # Generating subcircuit instance from the definition
    @property
    def subinst(self):
        try:
            if not hasattr(self,'_subinst'):
                if self.parent.model=='eldo':
                    startmatch=re.compile(r"\.SUBCKT %s " % self.parent.name.upper(),re.IGNORECASE)
                elif self.parent.model=='spectre':
                    startmatch=re.compile(r"\SUBCKT %s " % self.parent.name.upper(),re.IGNORECASE)
                subckt = self.subckt.split('\n')
                if len(subckt) <= 3 and not self.postlayout:
                    self.print_log(type='W',msg='No subcircuit found.')
                    self._subinst = "%s Empty subcircuit\n" % (self.parent.syntaxdict["commentchar"])
                else:
                    self._subinst = "%s Subcircuit instance\n" % (self.parent.syntaxdict["commentchar"])
                    startfound = False
                    endfound = False
                    lastline = False
                    # Extract the module definition
                    if not self._postlayout:
                        for line in subckt:
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
                                    words[0] = "X%s%s" % (self.parent.name.upper(),'' if self.parent.model == 'eldo' else ' (')
                                    words.pop(1)
                                    line = ' '.join(words)
                                self._subinst += line + "%s\n" % ('\\' if lastline else '')
                        self._subinst += '+' if self.parent.model == 'eldo' else ') '  + self.parent.name.upper()
                    else:
                        # This part is the above copy-pasted, only difference is that its read from a file
                        # TODO: needs obvious refactoring
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
            self.print_log(type='I',msg=traceback.format_exc())
            pdb.set_trace()
    @subinst.setter
    def subinst(self,value):
        self._subinst=value
    @subinst.deleter
    def subinst(self,value):
        self._subinst=None

if __name__=="__main__":
    pass
