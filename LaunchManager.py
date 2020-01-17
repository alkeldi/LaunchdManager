#!/usr/local/bin/python3
import sys
import pwd
import os
import subprocess
import json

def error(msg):
    print("Error: " + msg, file=sys.stderr)
    exit(1)

def printUsage():
    print("Usage:")
    print("\t" + sys.argv[0] + " [load|unload|enable|disable] [|agents|daemons] [|-system|-global|-user <user>] [<label>|-path <path>]")
    print("\t" + sys.argv[0] + " list [|loaded|unloaded] [|enabled|disabled|nooverride] [|agents|daemons] [|-system|-global|-user <user> ...]")
    print("\t" + sys.argv[0] + " users [|all]")
    sys.exit(1)

def getAllUsers():
    users = {}
    usersList = pwd.getpwall()
    for entry in usersList:
        users[entry.pw_name] = entry
    return users

def printUsers(isAll):
    users = getAllUsers()
    print("%-8s\t%-16s\t%-24s\t%s" %("UID", "Username", "Home", "Description"))
    print("%-8s\t%-16s\t%-24s\t%s" %("---", "--------", "----", "-----------"))
    for user in users:
        if not isAll and user[0] == '_':
            continue
        user = users[user]
        print("%-8s\t%-16s\t%-24s\t%s" %(user.pw_uid, user.pw_name, user.pw_dir, user.pw_gecos))

def compareOldAndNew(new, old):
    if new == old:
        return True
    if new == 'mach-port-object' or new == 'file-descriptor-object':
        return True
    if new == ['mach-port-object'] or new == ['file-descriptor-object']:
        return True
    if type(new) == type(old) and type(new) == dict:
        for key in new:
            if key in old:
                if not compareOldAndNew(new[key], old[key]):
                    return False
        return True
    return False
    error("compareOldAndNew: unknown case")


def runProcess(info, myinput = None):
    proc = subprocess.Popen(info, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    out, err = proc.communicate(input=myinput)
    proc.stdout.close()
    if proc.returncode != 0: error("can't comunicate with " + info[0] + ".")
    return out.decode("utf8")

def getLaunchsFromPlists(dirPath):
    result = {}
    if not os.path.isdir(dirPath):
        return result
    for filename in os.listdir(dirPath):
        if filename.endswith(".plist"):
            path = dirPath + '/' + filename
            out = runProcess(['plutil', '-convert', 'json', path, '-o', '-'])
            try: out = json.loads(out)
            except:
                print('unable to convert to JSON')
                sys.exit(1)
            out['PlistPath'] = path
            if 'Label' in out:
                result[out['Label']] = out
                result[out['Label']]['Loaded'] = False
            else:
                result[path] = out
                result[path]['Loaded'] = False
    return result

def findOwner(LaunchInfo, launchType, label):
    owner = None
    for domain in LaunchInfo:
        if domain == '-unknown':
            continue
        for l in LaunchInfo[domain][launchType]:
            if l == label:
                if owner:
                    error('duplicate onwer')
                else:
                    owner = domain
    return owner
    
def updateLaunchsDetails(LaunchInfo, launchType, options):
    if launchType != "agents"  and launchType != "daemons": error("panic (bad code block)")
    for domain in LaunchInfo:
        if domain == '-unknown': continue
        if domain == '-global' or domain == '-system':
            launchctlList = runProcess(['sudo', 'launchctl', 'list'])
        else:
            launchctlList = runProcess(['sudo', '-u', domain, 'launchctl', 'list'])
        
        launchctlList =  launchctlList.split('\n')[1:-1]
        for entry in launchctlList:
            entry = entry.split('\t')
            label = entry[2]
            exists = False
            if label in LaunchInfo[domain][launchType]:
                exists = True
                if domain == '-global' or domain == '-system':
                    launchctDetails = runProcess(['sudo', 'launchctl', 'list', label])
                else:
                    launchctDetails = runProcess(['sudo', '-u', domain, 'launchctl', 'list', label])

                launchctlDetailsJSON = runProcess(['./launchctlToJSON'], launchctDetails.encode())
                try: launchctlDetailsJSON = json.loads(launchctlDetailsJSON)
                except:
                    print('unable to convert to JSON')
                    sys.exit(1)
            if exists:
                for key in launchctlDetailsJSON:
                    if key in LaunchInfo[domain][launchType][label]:
                        if LaunchInfo[domain][launchType][label][key] != launchctlDetailsJSON[key]:
                            LaunchInfo[domain][launchType][label][str(key) + "::runtime"] = launchctlDetailsJSON[key]
                    else:    
                        LaunchInfo[domain][launchType][label][key] = launchctlDetailsJSON[key]
                LaunchInfo[domain][launchType][label]['Loaded'] = True

            else:
                if findOwner(LaunchInfo, launchType, label) == None:
                    LaunchInfo['-unknown'][launchType][label] = {'PID':entry[0], 'LastExitStatus':entry[1]}
            #         LaunchInfo['-unknown'][launchType][label]['Loaded'] = True
            #     if label == 'om.alkeldi.startup':
            #         print('here')
            #         sys.exit(1)
            

    return LaunchInfo

def printLaunchDetails(LaunchInfo):
    print("%s\t%s\t%-8s\t%s\t%-8s\t%-8s\t%s" %("pid", "exit", "load", "override", "type", "owner", "label"))
    print("%s\t%s\t%-8s\t%s\t%-8s\t%-8s\t%s" %("----", "-----", "-----", "---------", "-----", "------", "------"))
    for domain in LaunchInfo:
        for ltype in LaunchInfo[domain]:
            for label in LaunchInfo[domain][ltype]:
                pid = '?'
                exit_status = '?'
                load = 'unloaded'
                override = 'TODO'
                if "PID" in LaunchInfo[domain][ltype][label]:
                    pid = LaunchInfo[domain][ltype][label]["PID"]
                if "LastExitStatus" in LaunchInfo[domain][ltype][label]:
                    exit_status = LaunchInfo[domain][ltype][label]["LastExitStatus"]
                if "Loaded" in LaunchInfo[domain][ltype][label] and LaunchInfo[domain][ltype][label]['Loaded'] == True:
                    load = "loaded"
                print("%s\t%s\t%-8s\t%-8s\t%-8s\t%-8s\t%s" %(pid, exit_status, load, override, ltype[:-1], domain, label))

def makeLaunchsDetails(options):
    LaunchInfo = {'-unknown': {'agents': {}, 'daemons': {}}}
    if options['-global']:
        LaunchInfo['-global'] = {}
        if options['agents']: LaunchInfo['-global']['agents'] = getLaunchsFromPlists('/Library/LaunchAgents')
        if options['daemons']: LaunchInfo['-global']['daemons'] = getLaunchsFromPlists('/Library/LaunchDaemons')
    
    if options['-system']:
        LaunchInfo['-system'] = {}
        if options['agents']: LaunchInfo['-system']['agents'] = getLaunchsFromPlists('/System/Library/LaunchAgents')
        if options['daemons']: LaunchInfo['-system']['daemons'] = getLaunchsFromPlists('/System/Library/LaunchDaemons')

    if '-user' in options and len(options['-user']) >= 1:
        users = getAllUsers()
        for user in options['-user']:
            if user not in users: error('unkown username ('+ user +')')
            LaunchInfo[user] = {}
            if options['agents']: LaunchInfo[user]['agents'] = getLaunchsFromPlists(users[user].pw_dir + '/Library/LaunchAgents')
            if options['daemons']: LaunchInfo[user]['daemons'] = getLaunchsFromPlists(users[user].pw_dir +'/Library/LaunchDaemons')
    
    if options['daemons']:
        LaunchInfo = updateLaunchsDetails(LaunchInfo, 'daemons', options)

    if options['agents']:
        LaunchInfo = updateLaunchsDetails(LaunchInfo, 'agents', options)
    
    
    if not options['-allowners']:
        LaunchInfo['-unknown'] = {}

    toDelete = []
    for myDomain in LaunchInfo:
        for myType in LaunchInfo[myDomain]:
            for myLabel in LaunchInfo[myDomain][myType]:
                if not options['loaded'] and LaunchInfo[myDomain][myType][myLabel]['Loaded']:
                    toDelete.append({'domain': myDomain, 'ltype': myType, "label": myLabel})
                elif  not options['unloaded'] and not LaunchInfo[myDomain][myType][myLabel]['Loaded']:
                    print(myLabel)
                    toDelete.append({'domain': myDomain, 'ltype': myType, "label": myLabel})

    for element in toDelete:
        domain = element['domain']
        ltype = element['ltype']
        label = element['label']
        del LaunchInfo[domain][ltype][label]


    return LaunchInfo


def start():
    defaults = { 
        'list' : {
            "loaded": True, "unloaded": True, "enabled": True, "disabled": True, 
            "nooverride": True, "agents": True, "daemons": True, '-allowners': False, "-system": True,
            "-global": True, "-user": [pwd.getpwuid(os.getuid()).pw_name]
        }
    }
    if len(sys.argv) == 3 and sys.argv[1] == "users" and sys.argv[2] == "all":
        printUsers(True)
    elif len(sys.argv) == 2 and sys.argv[1] == "users":
        printUsers(False)
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        current_options = {}
        lookForUsername = False
        for option in sys.argv[2:]:
            if option == '-user' or (not lookForUsername and option in defaults['list'] and option not in current_options):
                if option == '-user': lookForUsername = True
                else: current_options[option] = True
            elif lookForUsername :
                if '-user' not in current_options: current_options['-user'] = [option]
                else: current_options['-user'].append(option)
                lookForUsername = False
            else: printUsage()
        if lookForUsername:
            printUsage()
        
        if 'loaded' in current_options or 'unloaded' in current_options:
            defaults['list']['loaded'] = False
            defaults['list']['unloaded'] = False
        if 'enabled' in current_options  or 'disabled' in current_options or 'nooverride' in current_options:
            defaults['list']['enabled'] = False
            defaults['list']['disabled'] = False
            defaults['list']['nooverride'] = False
        if 'agents' in current_options or 'daemons' in current_options:
            defaults['list']['agents'] = False
            defaults['list']['daemons'] = False
        if '-system' in current_options or '-global' in current_options or '-user' in current_options:
            defaults['list']['-system'] = False
            defaults['list']['-global'] = False
            defaults['list']['-user'] = []

        if '-allowners' in current_options:
            defaults['list']['-system'] = True
            defaults['list']['-global'] = True
            users = getAllUsers()
            defaults['list']['-user'] = []
            for user in users:
                defaults['list']['-user'].append(user)
            

        for option in defaults['list']:
            if option not in current_options:
                current_options[option] = defaults['list'][option]
        info = makeLaunchsDetails(current_options)
        printLaunchDetails(info)
    else:
        printUsage()
    

start()

