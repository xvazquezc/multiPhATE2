#############################################################
# Name: cgp_fastaSequence.py
#
# Programmer: Carol L. Ecale Zhou
#
# Last update: 16 October 2020
# 
# Module containing classes and methods for representing a multi-fasta sequence and associated methods
# Classes and methods: 
#     fasta
#         queryNRsequence
#         enterGeneData
#         enterProteinData
#         assignType
#         assignHeader
#         assignCompoundHeader
#         assignCustomHeader
#         assignContig
#         assignSequence
#         restoreSlashesAfterEMBOSS
#         removeEMBOSSpostfix
#         removeTerminalAsterisk
#         getFullHeader
#         getCleanHeader
#         getTruncHeader
#         getShortHeader
#         getCompoundHeader
#         getBlastHeader
#         getSequentialHeader
#         getCustomHeader
#         getHeader
#         getCustomHeader
#         getStartCodon
#         verifyProkaryoticStartCodon
#         highlightAllStartCodons
#         consolidate
#         getSequenceLength
#         getSubsequence
#         getPVOGassociationList
#         reverseComplement
#         addAnnotation
#     x   getStartCodon
#         printFasta
#         printHeaders
#         printFasta2file
#         printFasta2file_case
#         printAll
#         printAll_tab
#         printAll2file_tab
#         printData2file_GFF
#         printData2file
#         splitToList
#         getAnnotationlist
#         printAnnotations
#         printAnnotations_tab
#         printAnnotations2file_tab
#         printAnnotations2file
#     multiFasta   
#         reportStats
#         countParalogs
#         addFasta
#         addFastas
#         addFastasFromFile
#         addAnnotation
#         deleteFasta
#         printMultiFasta
#         printMultiFasta2file
#         printMultiFasta2file_case
#         printMultiFasta2file_custom
#         printAll
#         printAll2file
#         renumber
#         matchHeader
#         removeEMBOSSpostfix
#         removeTerminalAsterisk   
#
####################################################################    

# This code was developed by Carol L. Ecale Zhou at Lawrence Livermore National Laboratory.
# THIS CODE IS COVERED BY THE GPL3 LICENSE. SEE INCLUDED FILE GPL-3.PDF FOR DETAILS.

import re, string
from Bio.Seq import Seq
import cgp_annotation as annotation
from Bio import SeqIO  
import os

# Boolean control of verbosity

PHATE_PROGRESS = False
PHATE_MESSAGES = False
PHATE_WARNINGS = False

PHATE_PROGRESS_STRING = os.environ["PHATE_PHATE_PROGRESS"]
PHATE_MESSAGES_STRING = os.environ["PHATE_PHATE_MESSAGES"]
PHATE_WARNINGS_STRING = os.environ["PHATE_PHATE_WARNINGS"]

if PHATE_PROGRESS_STRING.lower() == 'true':
    PHATE_PROGRESS = True
if PHATE_MESSAGES_STRING.lower() == 'true':
    PHATE_MESSAGES = True
if PHATE_WARNINGS_STRING.lower() == 'true':
    PHATE_WARNINGS = True

CLEAN_RAW_DATA = os.environ["PHATE_CLEAN_RAW_DATA"]

#DEBUG = True
DEBUG = False  # For maximal verbosity

# For GFF formatting of output
EMPTY_COL      = '.' # Any column without data get a '.'
SEQID_COL      = 0   # First data column contains the sequence identifier: name of chromosome or scaffold
SOURCE_COL     = 1   # Name of the program that generated this feature, or the data source (database or project name)
TYPE_COL       = 2   # Type of feature; must be a term or accession from the SOFA sequence ontology (according to specs)
START_COL      = 3   # Start position on feature, with sequence numbering starting at 1
END_COL        = 4   # Start position on feature, with sequence numbering starting at 1
SCORE_COL      = 5   # A floating point value
STRAND_COL     = 6   # Defined as + (forward) or - (reverse)
PHASE_COL      = 7   # One of '0', '1', or '2'. '0' indicates that the 1st base of the feature is the first base of a codon....
ATTRIBUTES_COL = 8   # A semicolon-separated list of tag-value pairs, providing additional information about each feature.
                     # Some of these tags are predefined, eg, ID, Name, Alias, Parent (see GFF documentation).
GFF_SOURCE     = "PhATE"
GFF_SCORE      = EMPTY_COL  # blast hit stats will not be reported here
GFF_PHASE      = EMPTY_COL  # phase will not be reported here

# Patterns
p_extra      = re.compile('(\s)|([0-9])|(\*)') # characters often included in sequence text 
p_header     = re.compile('^>(.*)')
p_comment    = re.compile('^#')
p_up2space   = re.compile('^\S*')   # find 1st instance of everything that's not white space (check this)
p_startCodon = re.compile('atg')  # standard start codon sequence (recall: storing sequence as lower case)


#######################################################################################

class fasta(object):

    # Class fasta represents any kind of fasta sequence. User can specify a parent sequence,
    # comprising a header, for identifying a child relationship: eg, gene has a contig parent.
    # Fasta header is stored as text only, without the conventional '>'.
    # Get and print methods return header with the initial '>' symbol.
    # There is a need for multiple headers (e.g., header and shortHeader) because...
    # the header may be truncated after the first white space; the full header is
    # the entire header string provided by the user. (Note: RAST truncates header after space)
    # Sequence can be entered as a list of lines or as continuous sequence in a single string.
    # Sequence can be converted back & forth between lines vs. single string.

    def __init__(self):
        self.header = "unknown"           # full, original header
        self.cleanHeader = ""             # remove all special chars from original header
        self.truncHeader = ""             # truncated after N (self.truncation) characters
        self.shortHeader = ""             # truncated after 1st space (consistent w/RAST) 
        self.compoundHeader = ""          # header with parentSequence (eg, contig name) appended
        self.blastHeader = ""             # header that results from blast, which truncates after 1st space
        self.sequentialHeader = "hdr"     # an assigned, benign header that will not break 3rd party codes
        self.customHeader = ""            # a customized header; could be anything, but written for pVOGs
        self.name = "none"                # name will be geneCaller + number, if gene|protein from gene call
        self.sequence = ""                # store sequence as continuous lower-case string, sans numbers, white space
        self.sequenceType = "unknown"     # "nt" or "aa"; not "gene" or "dna" or the like
        self.moleculeType = "unknown"     # eg, 'contig', 'peptide', 'protein', or 'gene'
        self.parentSequence = ""          # eg, for gene, the contig that the gene is on
        self.truncation = 15              # number of characters (N) in header to retain, by default
        self.annotationList = []          # list of annotationRecord objects 
        self.paralogList = []             # list of paralog objects (header + blast hit)
        self.startCodonCount = 0          # calculated possible start codons in forward strand (for genes)
        self.codonStartLocs = []          # start positions of 'atg' (or alternate) sequences (for genes)
        self.start = 0                    # start on contig or gene (ie, parent structure)
        self.end = 0                      # end on contig or gene (ie, parent structure)
        self.parentName = ''              # name of parent sequence (eg, contig name or assigned gene name)
        self.parentStart = 0              # start position of parent (eg, parent gene) on its parent structure (eg, contig)
        self.parentEnd = 0                # end position of parent (eg, parent gene) on its parent structure (eg, contig)
        self.parentStrand = ''            # strand of parent sequence (eg, strand that gene was called on)
        self.strand = ''                  # strand, if gene (or protein, referring to parent gene)
        self.nrHeader = ""                # "combined" header from NR database sequence entry
        self.nrGInumber = ""              # NCBI gi identifier
        self.geneCallFile = "unknown"     # name of file containing gene calls
        self.geneCaller = "unknown"       # name of gene caller used to predict gene
        self.geneCallRank = 0             # priority label of gene call: lower number is more reliable (ie, 0 is best)
        self.nextFastaNumber = 0          # for assigning sequential, benign header (sequentialHeader)
        self.order = 0                    # order in multi-fasta list (i.e., order in which object was added by code)
        self.number = 0                   # number in list, if input in that manner (e.g., gene call; warning: external data)
        self.pVOGassociationList = []     # list of pVOGs associated with this fasta
        self.pVOGcount = 0                # for dignostics in constructing pVOG fasta data set
        self.contig = "unknown"           # name of contig this fasta is associated with

    def queryNRsequence(self,gi,nrLocation):  # Specific to NR; any other database has different format 
        # Given an NCBI gi identifier and the dir/file of an NR database, pull the sequence from NR database
        if gi != "" and int(gi) > 0: 
            giString = "gi\|" + gi + "\|"
        else:
            print("problem with gi")
            return(0)
        for record in SeqIO.parse(nrLocation,"fasta"):
            match = re.findall(giString,record.id)
            if match:
                self.assignHeader(record.id)
                self.assignSequence(str(record.seq))

    #*** Should collapse enterGeneData and enterProteinData as single method
    def enterGeneData(self,geneData): #*** should create a gene class, which "inherits" fasta
        if isinstance(geneData,dict): #*** should pass **kvargs and check for keys
            if "header" in list(geneData.keys()):
                self.assignHeader(geneData["header"])
            if "name" in list(geneData.keys()):
                self.name = geneData["name"]
            if "sequence" in list(geneData.keys()):
                self.sequence = geneData["sequence"]
            if "type" in list(geneData.keys()):
                self.sequenceType = geneData["type"]
            if "start" in list(geneData.keys()):
                self.start = geneData["start"]
            if "end" in list(geneData.keys()):
                self.end = geneData["end"]
            if "parentSequence" in list(geneData.keys()):
                self.parentSequence = geneData["parentSequence"]
            if "parentName" in list(geneData.keys()):
                self.parentName = geneData["parentName"]
            if "parentStart" in list(geneData.keys()):
                self.parentStart = geneData["parentStart"]
            if "parentEnd" in list(geneData.keys()):
                self.parentEnd = geneData["parentEnd"]
            if "order" in list(geneData.keys()):
                self.order = geneData["order"]
            return True
        else:
            return False

    def enterProteinData(self,proteinData): #*** should create a protein class, which "inherits" fasta
        if isinstance(proteinData,dict): #*** should pass **kvargs and check for keys
            if "header" in list(proteinData.keys()):
                self.assignHeader(proteinData["header"])
            if "name" in list(proteinData.keys()):
                self.name = proteinData["name"]
            if "sequence" in list(proteinData.keys()):
                self.sequence = proteinData["sequence"]
            if "type" in list(proteinData.keys()):
                self.sequenceType = proteinData["type"]
            if "start" in list(proteinData.keys()):
                self.start = proteinData["start"]
            if "end" in list(proteinData.keys()):
                self.end = proteinData["end"]
            if "parentSequence" in list(proteinData.keys()):
                self.parentSequence = proteinData["parentSequence"]
            if "parentName" in list(proteinData.keys()):
                self.parentName = proteinData["parentName"]
            if "parentStart" in list(proteinData.keys()):
                self.parentStart = proteinData["parentStart"]
            if "parentEnd" in list(proteinData.keys()):
                self.parentEnd = proteinData["parentEnd"]
            if "order" in list(proteinData.keys()):
                self.order = proteinData["order"]
            return True
        else:
            return False

    def assignType(self,mtype):
        if mtype.lower() == "nt" or mtype.lower() == "nucl" or mtype.lower() == "nucleotide":
            self.sequenceType = mtype.lower()
        elif mtype.lower() == "aa" or mtype.lower() == "amino-acid" or mtype.lower() == "protein" or mtype.lower() == "peptide":
            self.sequenceType = mtype.lower()
        else:
            self.sequenceType = "unknown"

    def assignHeader(self,hdr):   # Remove symbols and spaces, which may cause problems for open-source codes
        cleanHeader = hdr.lstrip('>') # Remove '>' symbol if present; store header text only
        self.header = cleanHeader  # Store full, original header, but without the '>'
        splitSpace = cleanHeader.split(' ') # Note: Blast truncates after the 1st space
        self.blastHeader = splitSpace[0] 
        cleanHeader = re.sub(' ', '_', cleanHeader)
        cleanHeader = re.sub('[();:?\.]','',cleanHeader)
        self.cleanHeader = cleanHeader
        self.truncHeader = self.header[0:self.truncation]
        # Assign a benign, sequential header 
        self.sequentialHeader = self.moleculeType + '-' + str(self.order)
        match = p_up2space.match(self.header)
        if match:
            self.shortHeader = match.group()
        else:
            self.shortHeader = self.truncHeader
        self.compoundHeader = self.header
        if self.parentSequence:
            self.compoundHeader = self.compoundHeader + '_' + self.parentSequence

    def assignCompoundHeader(self,hdr,parent):   
        # Creates a compound header; user should self.assignHeader first, then input self.cleanHeader as hdr
        self.compoundHeader = parent + '_' + hdr

    def assignCustomHeader(self,customHdr):
        self.customHeader = customHdr

    def assignContig(self,contigName):
        self.contig = contigName

    def assignSequence(self,seq):      # Input is single string or a list of strings
        if isinstance(seq,str):
            self.sequence = seq.lower()
            self.consolidate()         # Remove white spaces & numbers, if present
            return True
        elif isinstance(seq,list):
            self.sequence = ''.join(seq.lower())
            self.consolidate()         # Remove white space and collapse
            return True
        else:
            seqType = type(seq)
            return False

    def restoreSlashesAfterEMBOSS(self):
        pass

    def removeEMBOSSpostfix(self):  # Remove the pesky "_1" that EMBOSS adds
        self.assignHeader(self.header.rstrip("_1 "))

    def removeTerminalAsterisk(self):
        self.sequence = self.sequence.rstrip("* ")

    def getFullHeader(self):
        return ('>' + self.header)  # Add '>' symbol
 
    def getCleanHeader(self):
        return ('>' + self.cleanHeader)

    def getTruncHeader(self):
        return ('>' + self.truncHeader)

    def getShortHeader(self):  #
        return ('>' + self.shortHeader) 

    def getCompoundHeader(self):  # parentSequence (e.g., contig name) is appended to header 
        return ('>' + self.compoundHeader) 

    def getBlastHeader(self):
        return ('>' + self.blastHeader)

    def getSequentialHeader(self):
        return ('>' + self.sequentialHeader)

    def getCustomHeader(self):
        return ('>' + self.customHeader)
 
    def getHeader(self,hdrType):
        headerType = hdrType.lower()
        if headerType == 'full':
            return ('>' + self.header)
        elif headerType == 'clean':
            return ('>' + self.cleanHeader)
        elif headerType == 'trunc':
            return ('>' + self.truncHeader)
        elif headerType == 'short':
            return ('>' + self.shortHeader)
        elif headerType == 'compound':
            return ('>' + self.compoundHeader)
        elif headerType == 'blast':
            return ('>' + self.blastHeader)
        elif headerType == 'sequential':
            return ('>' + self.sequentialHeader)
        elif headerType == 'custom':
            return ('>' + self.customHeader)
        else:
            if PHATE_WARNINGS == 'True':
                print("cgp_fastaSequence says, WARNING: Invalid header type:", hdrType, "--Choose full, clean, trunc, short, compound, blast")

    def getStartCodon(self):
        if self.sequence != "":
            return self.sequence[0:3]
        else:
            return False 

    def verifyProkaryoticStartCodon(self):
        if self.sequence != "":
            testCodon = self.sequence[0:3].lower()
            if testCodon == "atg":
                return "common"
            elif testCodon == "gtg" or testCodon == "ttg":
                return "alternate"
            elif testCodon == "att" or testCodon == "ctg":
                return "rare"
            else:
                return "incorrect"

    def highlightAllStartCodons(self):
        codonStarts = []
        seqList = list(self.sequence)
        codonsHighlighted = ""
        if self.sequence != "":
            codonStarts = [m.start() for m in re.finditer('atg',self.sequence)]
            self.startCodonCount = len(codonStarts)
            for start in codonStarts:
                seqList[start] = seqList[start].upper()
                seqList[start+1] = seqList[start+1].upper()
                seqList[start+2] = seqList[start+2].upper()
            codonsHighlighted = ''.join(seqList)
            self.codonStartLocs = codonStarts
        return codonsHighlighted 

    def consolidate(self): # Remove white space and collapse sequence
        self.sequence = p_extra.sub('',self.sequence) # 

    def getSequenceLength(self):
        return (len(self.sequence))     # Report how long the sequence is

    def getSubsequence(self,start,end): # Recall: string position numbering starts with 0!
        return (self.sequence[int(start):int(end)])

    def getPVOGassociationList(self):
        return (self.pVOGassociationList)

    def reverseComplement(self):
        if self.sequenceType.lower() == "nt":
            tempSeq = Seq(self.sequence)
            self.sequence = tempSeq.reverse_complement()
            return True
        return False

    def addAnnotation(self,newAnnot):
        self.annotationList.append(newAnnot)

    def printFasta(self):
        hdr = self.getFullHeader()
        seq = self.sequence
        print(hdr)
        print(seq)

    def printHeaders(self):
        print("header:",self.header)
        print("cleanHeader:",self.cleanHeader)
        print("truncHeader:",self.truncHeader)
        print("shortHeader:",self.shortHeader)
        print("compoundHeader:",self.compoundHeader)
        print("blastHeader:",self.blastHeader)
        print("sequentialHeader:",self.sequentialHeader)
        print("customHeader:",self.customHeader)

    def printFasta2file(self,FILE_HANDLE,headerType="short"):
        if headerType.lower() == "compound":
            hdr = self.getCompoundHeader()
        elif headerType.lower() == "full":
            hdr = self.getFullHeader()
        elif headerType.lower() == "truncated":
            hdr = self.getTruncHeader()
        elif headerType.lower() == "short":
            hdr = self.getShortHeader()
        elif headerType.lower() == "blast":
            hdr = self.getBlastHeader()
        elif headerType.lower() == "sequential":
            hdr = self.getSequentialHeader()
        elif headerType.lower() == "custom":
            hdr = self.getCustomHeader()
        else:
            hdr = self.getShortHeader()
        seq = self.sequence
        FILE_HANDLE.write("%s%s" % (hdr,"\n"))
        FILE_HANDLE.write("%s%s" % (self.sequence,"\n"))

    def printFasta2file_case(self,FILE_HANDLE,case,headerType="short"):
        if headerType.lower() == "compound":
            hdr = self.getCompoundHeader()
        elif headerType.lower() == "full":
            hdr = self.getFullHeader()
        elif headerType.lower() == "truncated":
            hdr = self.getTruncHeader()
        elif headerType.lower() == "short":
            hdr = self.getShortHeader()
        elif headerType.lower() == "sequential":
            hdr = self.getSequentialHeader()
        else:
            hdr = self.getShortHeader()
        seq = self.sequence
        if case.lower() == "upper":
            seq = seq.upper()
        FILE_HANDLE.write("%s%s" % (hdr,"\n"))
        FILE_HANDLE.write("%s%s" % (seq,"\n"))

    def printAll(self):  # Dump everything: useful for testing  
        print("Header:                   ", self.header)
        print("CleanHeader:              ", self.cleanHeader)
        print("TruncHeader:              ", self.truncHeader)
        print("ShortHeader:              ", self.shortHeader)
        print("CompoundHeader:           ", self.compoundHeader)
        print("BlastHeader:              ", self.blastHeader)
        print("SequentialHeader:         ", self.sequentialHeader)
        print("Name:                     ", self.name)
        print("Type:                     ", self.sequenceType)
        print("ParentName:               ", self.parentName)
        print("ParentSequence:           ", self.parentSequence)
        print("ParentStart:              ", self.parentStart)
        print("ParentEnd:                ", self.parentEnd)
        print("Order in multi-fasta list:", self.order)
        print("Truncation:               ", self.truncation)
        print("Start codon count:        ", self.startCodonCount)
        print("Codon start locations:")
        if self.codonStartLocs:
            for location in self.codonStartLocs:
                print("   ", location)
            print('\n')
        else:
            print("none")
        print("Sequence length is:", self.getSequenceLength())
        count = 0
        if self.annotationList:
            count += 1
            self.printAnnotations()
        else:
            print("There are no annotations")
        count = 0
        if self.paralogList:
            for paralog in self.paralogList:
                count += 1
                print("Paralog No.", count, ":", paralog)
        else:
             print("Paralog detection not yet in service")  #***
        print("Sequence:", self.sequence)

    def printAll_tab(self):
        tabLine = 'Header:' + self.header + '\tName:' + self.name + '\tType:' + self.sequenceType + '\tOrder:' + str(self.order)
        print(tabLine)
        if self.annotationList:
            self.printAnnotations_tab()
        else:
            print("There are no annotations")
        if len(self.sequence) < 1000:
            print(self.sequence)
        else:
            print("Sequence too long to print. See file.")

    def printAll2file_tab(self,FILE_HANDLE):
        tabLine = 'Header:' + self.header + '\tName:' + self.name + '\tType:' + self.sequenceType + '\tOrder:' + str(self.order) + '\tparent:' + str(self.start) + '/' + str(self.end) + '/' + str(self.strand) + '/' + self.parentName + '\tlength: ' + str(len(self.sequence))
        FILE_HANDLE.write("%s\n" % (tabLine))
        if self.annotationList:
            self.printAnnotations2file_tab(FILE_HANDLE)
        else:
            FILE_HANDLE.write("%s\n" % ("There are no annotations"))
        if len(self.sequence) < 1000:
            FILE_HANDLE.write("%s\n" % (self.sequence))
        else:
            FILE_HANDLE.write("%s\n" % ("Sequence too long to print. See file."))

    def printData2file_GFF(self,FILE_HANDLE,feature,contigName):
        # Note: pragmas are printed by calling method (ex: phate_genomeSequence/printGenomeData2file_GFF)
        GFF_annotationString = ''
        GFF_type = "unknown"
        FIRST = True

        # Construct data fields
        GFF_parentName = self.parentName        # column 1
        GFF_source     = GFF_SOURCE             # column 2

        if self.moleculeType == 'peptide' or self.moleculeType == 'protein' or self.sequenceType == 'aa' or feature == 'CDS':
            GFF_type   = "CDS"                  # column 3
            GFF_start  = str(self.parentStart)  # column 4
            GFF_end    = str(self.parentEnd)    # column 5
        elif self.moleculeType == 'gene' or self.sequenceType == 'nt' or feature == 'gene':
            GFF_type   = "gene"                 # column 3
            GFF_start  = str(self.start)        # colunn 4
            GFF_end    = str(self.end)          # column 5

        GFF_score      = GFF_SCORE              # column 6
        GFF_strand     = self.strand            # column 7
        GFF_phase      = GFF_PHASE              # column 8

        # Last one is complicated...
        # Column 9 has many sub-fields, starting with sequence identifier and parent
        if self.moleculeType == 'peptide' or self.moleculeType == 'protein' or self.sequenceType == 'aa':
            GFF_identifier = "ID=" + self.header + "_cds"
        elif self.moleculeType == 'gene' or self.sequenceType == 'nt':
            GFF_identifier = "ID=" + self.header

        # Write 1st 8 columns of data to file
        FILE_HANDLE.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t" % (contigName,GFF_source, GFF_type,GFF_start,GFF_end,GFF_score,GFF_strand,GFF_phase))

        # Write identifier to column 9
        FILE_HANDLE.write("%s%s" % (GFF_identifier, ';'))

        # Column 9 has many sub-fields, continuing with the annotation homologies
        count = 1
        if len(self.annotationList) > 0:
            for annotation in self.annotationList:
                annotNo = "annot" + str(count) + '='
                if fIRST:
                    FILE_HANDLE.write("%s" % (annotNo))
                    annotation.returnGFFannotationRecord(FILE_HANDLE)
                    FIRST = False
                else:
                    FILE_HANDLE.write("%s%s" % ('; ',annotNo))
                    annotation.returnGFFannotationRecord(FILE_HANDLE)
                count += 1
        FILE_HANDLE.write("\n" % ())

    #*** Fill out this method as printAll() above
    def printAll2file(self,FILE_HANDLE):  # Dump everything: useful for testing  
        count = 0 
        FILE_HANDLE.write("%s%s%s" % ("Header:",self.header,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("ShortHeader:",self.shortHeader,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("TruncHeader:",self.truncHeader,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("BlastHeader:",self.blastHeader,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("SequentialHeader:",self.sequentialHeader,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("Type:",self.sequenceType,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("Order in list:",self.order,"\n"))
        FILE_HANDLE.write("%s%s%s" % ("Sequence length is:",self.getSequenceLength(),"\n"))
        if (self.annotationList):
            count += 1
            FILE_HANDLE.write("%s%s%s" % ("Annotation Set No.",count,":\n"))
            self.printAnnotations2file(FILE_HANDLE)
        FILE_HANDLE.write("%s%s%s" % ("Sequence:",self.sequence,"\n"))

    def splitToList(self,lineLength):  # Returns a list of sequence lines
        nextLine = ""
        sequenceList = []
        numberList = list(range(0,len(self.sequence),lineLength))
        for number in numberList:
            nextSegment = self.sequence[int(number):int(number+lineLength)]
            sequenceList.append(nextSegment)
        return(sequenceList)
 
    def getAnnotationList(self):
        return self.annotationList

    def printAnnotations(self):  # Verbose outout
        count = 0
        for annot in self.annotationList:
            count += 1
            print("Annotation item", count)
            print('Source\tMethod\tType\t')
            annot.printAnnotationRecord()

    def printAnnotations_tab(self): # Streamlined output
        if self.annotationList != []:
            FIRST = True
            for annot in self.annotationList:
                if FIRST:
                    annot.printAnnotationRecord_tabHeader()
                    FIRST = False
                annot.printAnnotationRecord_tab()

    def printAnnotations2file_tab(self,FILE_HANDLE): # Streamlined output
        if self.annotationList != []:
            FIRST = True
            for annot in self.annotationList:
                if FIRST:
                    annot.printAnnotationRecord2file_tabHeader(FILE_HANDLE)
                    FIRST = False
                annot.printAnnotationRecord2file_tab(FILE_HANDLE)

    def printAnnotations2file(self,FILE_HANDLE):
        count = 0
        for annot in self.annotationList:
            count += 1
            FILE_HANDLE.write("%s%s\n" % ("Annotation item ",count))
            annot.printAnnotationRecord2file(FILE_HANDLE)

#####################################################################################
 
class multiFasta(object): 
 
    # Class multiFasta is essentially a list of fasta objects.
    # Usage: Draft or finished genome; set of genes or proteins
    # The class keeps track of the order in which the fasta objects occur in the list.
    # The order is needed so that it can be re-ordered based on, for example,
    # ...shifting the start position on the genome.

    def __init__(self):
        self.fastaList      = []  # list of fasta objects
        self.annotationList = []
        self.filename       = 'unknown'
        self.moleculeType   = 'unknown'
        self.contig         = 'unknown'  # redundant (use parentName)
        self.parentName     = ''         # contig name for gene or protein set; genome name for contig set

    def findStringInHeader(self,searchString):
        found = False
        for fasta in self.fastaList:
            match_string2header = re.search(searchString,fasta.header)
            if match_string2header:
                return(fasta)
        if PHATE_WARNINGS == 'True':
            print("cgp_fastaSequence says, WARNING: Fasta not found for", searchString)
        return(0)

    def reportStats(self):
        stats = []
        stats.append("Sequence from file name:" + self.filename)
        stats.append("Number of fasta sequence:" + str(len(self.fastaList)))
        stats.append("Number of annotations:" + str(len(self.annotationList)))
        stats.append("No. of fasta sequence with paralogs: " + str(self.countParalogs()))
        if PHATE_MESSAGES:
            print("Sequence from file name:", self.filename)
            print("Number of fasta sequences:", len(self.fastaList))
            print("Number of annotations:", len(self.annotationList))
            print("Annotations:", self.annotationList)
            print("No. of fasta sequences with paralogs:", self.countParalogs()) 
        return stats

    def countParalogs(self):  # count no. of fastas that have paralogs (not total paralog hits)
        count = 0
        for fasta in self.fastaList:
           if fasta.paralogList:
               count += 1 
        return count

    def assignContig(self,contigName):
        self.contig = contigName

    def assignContig2all(self,contigName):
        for fa in self.fastaList:
            fa.assignContig(contigName)

    def assignParent(self,parentName):
        self.parentName = parentName

    def assignCompoundHeaders(self,prependString):
        for fa in self.fastaList:
            fa.assignCompoundHeader(prependString)

    def assignMoleculeType(self,molType):
        for fasta in self.fastaList:
            fasta.moleculeType = molType

    def addFasta(self,newFa):
        newFa.order = len(self.fastaList) + 1
        newFa.moleculeType = self.moleculeType
        self.fastaList.append(newFa)

    def addFastaWithMetadata(self,newFa,metaData):
        if isinstance(metaData,dict):
            if "annotationList" in list(metaData.keys()):
                newFa.annotationList = metaData["annotationList"]
            if "contig" in list(metaData.keys()):
                newFa.contig = metaData["contig"]
        newFa.order = len(self.fastaList) + 1
        newFa.moleculeType = self.moleculeType
        self.fastaList.append(newFa)
        return

    def addFastas(self,lines,mtype): # Given multi-fasta file read into line set, create multi-fasta object
        sequence = ""
        numberAdded = 0
        if lines:
            header = lines[0] # capture 1st header (should be first line in lineSet!)
            lines.pop(0)
            for line in lines:
                match = re.search(p_header, line) # detect start of a new fasta
                if match:
                    newFasta = fasta()            # create new object
                    newFasta.moleculeType = self.moleculeType
                    numberAdded += 1              # no. of fasta objects added so far from lines
                    newFasta.order = numberAdded
                    newFasta.assignHeader(header) # 
                    newFasta.assignSequence(sequence)
                    newFasta.assignType(mtype)
                    self.addFasta(newFasta)
                    sequence = ""                 # reset
                    header = line                 # capture next header
                    continue
                sequence += line
            newFasta = fasta()
            newFasta.moleculeType = self.moleculeType
            numberAdded += 1              # no. of fasta objects added so far from lines
            newFasta.order = numberAdded
            newFasta.assignHeader(header)
            newFasta.assignSequence(sequence)
            newFasta.assignType(mtype)
            self.addFasta(newFasta)
            numberAdded += 1
        return numberAdded

    def addFastasFromFile(self,mtype):
        if self.filename == "unknown" or self.filename == '':
            if PHATE_WARNINGS == 'True':
                print("cgp_fastaSequence says, ERROR: First you must set the filename in addFastasFromFile()")
        else:
            fastaFile = open(self.filename,"r")
            fLines = fastaFile.read().splitlines()
            self.addFastas(fLines,mtype)

    def addAnnotation(self,newAnnot):
        self.annotationList.append(newAnnot)

    def deleteFasta(self,oldFasta):
        for fa in self.fastaList:
            if fa == oldFasta:
                self.fastaList.remove(fa)
                return True
        return False

    def printMultiFasta(self):
        for fa in self.fastaList:
            fa.printFasta()

    def printMultiFasta2file(self,FILE_HANDLE):
        for fa in self.fastaList:
            fa.printFasta2file(FILE_HANDLE)

    def printMultiFasta2file_case(self,FILE_HANDLE,case):
        for fa in self.fastaList:
            fa.printFasta2file_case(FILE_HANDLE,case)

    def printMultiFasta2file_custom(self,FILE_HANDLE):
        for fa in self.fastaList:
            if fa.customHeader:  # If the custom header is not empty string, then ok to print
                fa.printFasta2file(FILE_HANDLE,"custom")

    def printAll(self):
        count = 0
        print("Number of fastas:", len(self.fastaList))
        for fa in self.fastaList:
            count += 1
            print("*****List item no.", count, ":")
            fa.printAll()
            print("\n")

    def printAll2file(self,FILE_HANDLE):
        count = 0
        FILE_HANDLE.write("%s%s%s" % ("Number of fastas:",len(self.fastaList),"\n"))
        for fa in self.fastaList:
            count += 1
            FILE_HANDLE.write("%s%s%s" % ("*****List item no.",count,":\n"))
            fa.printAll2file(FILE_HANDLE)
            FILE_HANDLE.write("%s" % ("\n"))

    def renumber(self):  # If any fasta object was deleted, then renumber to close gaps in ordering
        newOrder = 0     # Caution:  this will re-order fasta objects in sequence!
        for fa in self.fastaList:
            newOrder += 1
            fa.order = newOrder 

    def matchHeader(self,hdr):
        for fa in self.fastaList:
            if fa.header == hdr:
                return fa
        return False

    def removeEMBOSSpostfix(self):  # remove pesky '_1' that EMBOSS adds to translated sequence
        for prot in self.fastaList:
            prot.removeEMBOSSpostfix()

    def removeTerminalAsterisk(self):  # remove '*' that EMBOSS adds to end of protein translation 
        for prot in self.fastaList:
            prot.removeTerminalAsterisk()
