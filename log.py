import time

logStart = time.time()
lastCheck = time.time()
logsCount = 0
logPrio  = 5
def log(*argv,prio = 5) :
    global logStart,lastCheck,logsCount,logPrio
    now = time.time()
    if prio >= logPrio :
        logsCount += 1
        print(f"{(now-logStart):8.2f}",*argv)
    elapsed = now-lastCheck
    if elapsed > 10 :
        if logsCount > 100 :
            logPrio += 1
        if logsCount < 10 :
            logPrio -=1
        lastCheck = now
        logsCount = 0
