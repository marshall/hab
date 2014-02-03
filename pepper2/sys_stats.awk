BEGIN {
    FS = "[ \t%-,:]+"
    uptime = "0"
    cpu_usage = "0"
    free_mem = "0"
    total_mem = "0"
    total_procs = "0"
}

NR==1 {
    uptime = $7 * 60
    uptime += $8
}

NR==2 {
    total_procs = $2
}

NR==3 {
    cpu_usage = 100 - $9
}

NR==4 {
    gsub("k", "", $6)
    gsub("k", "", $2)
    free_mem = $6
    total_mem = $2
}

END {
    printf "{"
    printf "\"uptime\": %d,", uptime
    printf "\"total_procs\": %s,", total_procs
    printf "\"cpu_usage\": %s,", cpu_usage
    printf "\"total_mem\": %s,", total_mem
    printf "\"free_mem\": %s", free_mem
    print "}"
}
