#!/usr/local/bin/python3
import sys
import os
import shutil
import json
from subprocess import Popen, PIPE
import re

#Setup Program
UID = str(os.getuid())
ROOT = 'root'
required_programs = {'sudo': None, 'plutil': None, 'launchctl': None}
launchctlList = {ROOT: {}, UID: {}}

def error(msg):
    print("Error: " + msg, file=sys.stderr)
    sys.exit(1)

def getlaunchctlList(isroot):
    #select privilge
    user = None
    if isroot:
        proc = Popen([required_programs['sudo'], required_programs['launchctl'], 'list'], stdout=PIPE)
        user = ROOT
    else:
        proc = Popen([required_programs['launchctl'], 'list'], stdout=PIPE)
        user = UID
    
    #run launchctl and obtain output
    out, err = proc.communicate()
    proc.stdout.close()
    if proc.returncode != 0:
        error("filed to execute launchctl")
    out = out.decode("utf8").split('\n')[1:-1]
    for entry in out:
        entry = entry.split('\t')
        if entry[2] in launchctlList[user]:
            error("duplicate entry in launchctl output '" + entry[2] + "'")
        launchctlList[user][entry[2]] = None


def launchctlEntryToDict(out):
    ####################### Simple equals #######################
    out = re.sub(r" = (\".*\");\n", r': \1,\n', out)
    ###################### Fix dictionaries #####################
    out = re.sub(r"(\".*\") = {\n", r'\1: {\n', out)
    ######################## Fix arrays #########################
    out = re.sub(r"(\".*\") = \(\n", r'\1: [\n', out)
    out = re.sub(r"\);\n", r'],\n', out)
    ####################### Qoute Values ########################
    out = re.sub(r' = ([^"^\n]+);\n', r': "\1",\n', out)
    out = re.sub(r'([^ ^\t^\n^;^}^\]^"]+);\n', r'"\1",\n', out)
    ########### Convert remaining semicolons to commas ##########
    out = re.sub(r';\n', r',\n', out)
    ################# Remove tabs and newlines ##################
    out = re.sub(r'[\t\n]', r'', out)
    ################### Remove trailing commas ##################
    out = re.sub(r',(}|\])', r'\1', out)
    out = out[:-1]
    # print(out)
    return out

#verify required programs
for name in required_programs:
    path = shutil.which(name)
    if path:
        required_programs[name] = path
    else:
        error(name + " is missing")    

#Obtain launchctlList
getlaunchctlList(False)
getlaunchctlList(True)

# Add info to launchctlList
for user in launchctlList:
    for label in launchctlList[user]:
        if user == ROOT:
            proc = Popen([required_programs['sudo'], required_programs['launchctl'], 'list', label], stdout=PIPE)
        else:
            proc = Popen([required_programs['launchctl'], 'list', label], stdout=PIPE)
        out, err = proc.communicate()
        out = out.decode("utf8")
        if proc.returncode != 0:
            error("filed to execute launchctl")
        out = launchctlEntryToDict(out)
        launchctlList[user][label] = json.loads(out)


lunchd = launchctlList[ROOT]['com.alkeldi.startup']
print(lunchd)
