#!/bin/zsh

#Navigate to this directory
cd /Users/ali/scripts
setopt +o nomatch

#Directories
directories=(
    $HOME/Library/LaunchAgents
    /Library/LaunchAgents
    /Library/LaunchDaemons
    #  /System/Library/LaunchAgents
    # /System/Library/LaunchDaemons
)


printf '%-6s %-6s %-10s %-10s %-8s %s\n' "PID" "Exit" "Load" "Override" "Type" "Label (Path)"
printf '\n'
for dir in $directories; do
    for filename in $dir/*.plist; do
        #handle empty directories
        if test "$(basename $filename)" == "*.plist"
        then
            continue
        fi

        #obtain Label
        label=$(/usr/libexec/PlistBuddy -c "print :Label" $filename 2> /dev/null)        
        if test "$label" == ""
        then
            label="<empty>"
        fi

        #obtain info
        info=
        override_info=
        load=
        pid=
        exit_code=
        Type=

        if test "$(basename $dir)" == "LaunchAgents"
        then
            override_info=$(/usr/libexec/PlistBuddy -c "print :$label" /var/db/com.apple.xpc.launchd/disabled.`id -u`.plist 2> /dev/null)
            info=$(launchctl list | grep "$label$")
            type="Agent"
        else
            override_info=$(/usr/libexec/PlistBuddy -c "print :$label" /var/db/com.apple.xpc.launchd/disabled.plist 2> /dev/null)
            info=$(sudo launchctl list | grep "$label")
            type="Daemon"
        fi

        #obtain load, pid, and exit status
        if test "$info" == ""
        then
            load="unloaded"
            pid="-"
            exit_code="-"
        else
            load="loaded"
            pid=$(echo $info | awk '{print $1}')
            exit_code=$(echo $info | awk '{print $2}')
        fi

        #obtain override
        override=
        if test "$override_info" == "true"
        then
            override="disabled"
        elif test "$override_info" == "false"
        then
            override="enabled"
        else
            override="_"
        fi

        printf '%-6s %-6s %-10s %-10s %-8s %s\n' "$pid" "$exit_code" "$load" "$override" "$type" "$label ($filename)"
    done
done

