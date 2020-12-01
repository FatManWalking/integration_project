
# Get OSM file from https://download.geofabrik.de/europe/germany/baden-wuerttemberg/karlsruhe-regbez-latest.osm.bz2
# or https://overpass-api.de/api/map?bbox=8.3786,49.4374,8.6035,49.5394 for Mannheim
# or https://overpass-api.de/api/map?bbox=8.4669,49.4628,8.5762,49.5111 for the area around DHBW Coblitzallee/Kaefertal
# 
# Shrink files a bit by dropping timestamp, changeset and uid information:
#    cat map.osm|sed -e's/ timestamp=".*"//g'|sed -e 's/ changeset=".*"//g'|sed -e 's/ uid=".*"//g' > shorter.osm
#
# install osmium by "pip install osmium"

from typing import Dict, Tuple

import math
import matplotlib.pyplot as plt

import os

from log import log 
from OSMHandler import OSMHandler

# Change this to your downloaded OSM file
osmfile = "mannheim-dbhw.osm"

if not os.path.exists(osmfile) :
    from six.moves import urllib 
    log("No OSM file",osmfile,"found. Downloading default area.")
    osmfile = "mannheim-dbhw.osm"
    urllib.request.urlretrieve("http://overpass-api.de/api/map?bbox=8.4669,49.4628,8.5762,49.5111",osmfile)
    log("Download of",osmfile,"done")

#
# There are two models for rules:
#
# Consider a way with tags "highway=service" and "foot=yes" and 
# rules for "highway==service":(10,0) and "higway==service && foot==yes":(2,0).
#
# In mode "override=True" the detailed rule (first rule plus more entries) 
# overrides the simple first rule, resulting in penalty (2,0) for the way.
# Negative total penalties are prevented by just non-negative weights.
#
# In mode "override=False" both applicable rules are added to penalty (12,0).
# While negative penalties for a rule are permissable, there is quite some effort
# to prevent negative total penalties, but this mode is easier to predict in
# the learning phase. The current learning method cannot result in negative 
# penalties for a rule, so this mode can be assumed to be less general for the
# same amount of rules.
# 

override = True 
            
log("Start loading map data")
osmhandler = OSMHandler(override)
#osmhandler.apply_file("Projects/Lectures/Integrationsseminar-WS-2020/Routrainer/mannheim-dhbw-shorter.osm")
osmhandler.apply_file(osmfile)
log("Finished loading map data")

# Node 840917640 is at the DHBW Campus Coblitzallee
log("Eingang DHBW Campus Coblitzallee:")
log(osmhandler.nodes[840917640],osmhandler.nodes[840917640].url()) # DHBW Campus Coblitzallee

# All ways with their nodes at that node 840917640:
for wid,nodes in osmhandler.nodes[840917640].ways.items() :
    log(osmhandler.ways[wid],nodes,osmhandler.ways[wid].url())

log("Press Return")
input()

log("Eingang DHBW Campus Käfertal")
log(osmhandler.nodes[2235009413]) # DHBW Campus Käfertal
log("Trivial Routing von Coblitzallee nach Käfertal")
(cost,path)=osmhandler.multiRoute([840917640,2235009413])
log("Open",osmhandler.gpxFromNodeList([nodeid for (_,nodeid,_,_) in path]),"in GPX viewer as https://www.j-berkemeier.de/ShowGPX.html")
log("Press Return")
input()

if override == False :
    exampleRules = { "W:sidewalk==no" :                             ( 10,   0),
                    "W:foot==no" :                                 (100,   0),
                    "N:foot==no" :                                 (  0,1000),
                    "W:sidewalk==separate" :                       (100,   0),
                    "W:highway==trunk" :                           ( 20,   0),
                    "N:crossing==no" :                             (  0, 100),
                    "W:lanes==2" :                                 ( 10,   0),
                    "W:lanes==2 && W:sidewalk==both" :             (-10,   0),
                    "W:highway==primary" :                         ( 30,   0),
                    "W:highway==primary && W:sidewalk==both" :     (-27,   0),
                    "W:highway==secondary" :                       ( 20,   0),
                    "W:highway==secondary && W:sidewalk==both" :   (-18,   0),
                    "W:highway==tertiary" :                        ( 10,   0),
                    "W:highway==tertiary && W:sidewalk==both" :    ( -9,   0) } 
else:
    exampleRules = { "W:sidewalk==no" :                             ( 10,   0),
                    "W:foot==no" :                                 (100,   0),
                    "N:foot==no" :                                 (  0,1000),
                    "W:sidewalk==separate" :                       (100,   0),
                    "W:highway==trunk" :                           ( 20,   0),
                    "N:crossing==no" :                             (  0, 100),
                    "W:lanes==2" :                                 ( 10,   0),
                    "W:lanes==2 && W:sidewalk==both" :             (  0,   0),
                    "W:highway==primary" :                         (  3,   0),
                    "W:highway==primary && W:sidewalk==both" :     (0.3,   0),
                    "W:highway==secondary" :                       (  2,   0),
                    "W:highway==secondary && W:sidewalk==both" :   (0.2,   0),
                    "W:highway==tertiary" :                        (  1,   0),
                    "W:highway==tertiary && W:sidewalk==both" :    (0.1,   0) } 


def combinations(src,depths,combine=" && ",prefix="") :
    """Compute all rule combinations for given simple rules up to a given depth"""
    target = []
    remain = src
    for entry in src :
        target += [prefix+entry]
        if depths > 0 :
            remain = [e2 for e2 in remain if e2!=entry]
            target += combinations( remain , depths-1 , combine=combine , prefix = prefix+entry+combine )
    return target

def rulesToDictTuple(rules,result = None):
    """Generate fast dict structure for list of rules as strings"""
    if result == None : 
        result = (dict(),dict())
    for rule,score in rules.items() :
        
        parts = rule.split(" && ",1)
        part1 = parts[0]
        kind  = part1.split(":",1)
        kind1 = kind[0]
        
        if kind1 == 'N' : 
            t = 0
        else :
            t = 1  

        rule = kind[1]        
        if len(parts)==1 :
            if rule in result[t] :
                (_,olddict) = result[t][rule]
                result[t][rule] = (score,olddict)
                
            else :
                result[t][rule] = (score,(dict(),dict()))
                
        else :
            if rule in result[t] :
                (oldscore,olddicttuple) = result[t][rule]
                newdicttuple = rulesToDictTuple({parts[1]:score},olddicttuple)
                result[t][rule] = (oldscore,newdicttuple)
                
            else :
                result[t][rule] = ((0,0),rulesToDictTuple({parts[1]:score}))
                
    return result

# Disregard these tags at all.
killTags = { "source", "source:geometry", "source:maxspeed", "name", "note", "area", "wikidata", "layer", "railway:pos", 
             "wikipedia", "ref", "old_old_name", "old_name", "ref:RNV:RBL" , "start_date", "created_by", "railway:signal:speed_limit",
             "end_date", "workrules", "operator", "destination", "admin_level" , "railway:position" , "railway:position:exact" ,
             "railway:signal:crossing:states", "ele" , "railway:signal:position", "lcn_ref" }

def usedTagsFromPath(path,dictTupleRules=(dict(),dict())) -> Dict[ str , Tuple[ float , float ] ] :
    """Deduce all rules used for this path as dict with length for ways and count for node rules"""
    allTags = dict()

    lastnode = osmhandler.nodes[path[0][1]]

    for wid,nid,_,length in path :
        way  = osmhandler.ways[wid]
        nextnode = osmhandler.nodes[nid]
        used = osmhandler.penaltyRules(dictTupleRules,lastnode,nextnode,way)
        lastnode = nextnode
        for rule in used :
            (oldlength,oldcount) = (0,0)
            if rule in allTags :
                (oldlength,oldcount) = allTags[rule]
            if rule.count("W:") > 0 :
                if rule.count("N:") > 0 : 
                    allTags[rule] = (oldlength+length,oldcount+1)
                else :
                    allTags[rule] = (oldlength+length,oldcount)
            else :
                allTags[rule] = (oldlength,oldcount+1)
        
    return allTags

def tagsFromPath(path,depth = 1) -> Dict[ str , Tuple[ float , float ] ] :
    """Deduce all possible rules that could be used on a given path up to a given depth"""
    allTags = dict()

    lastTags = set()

    for wid,nid,_,length in path :
        # if length>0 : maybe exclude the first step
        way  = osmhandler.ways[wid]
        node = osmhandler.nodes[nid]

        ctags = [ "W:"+tag+"=="+value for tag,value in way.tags.items() if not tag in killTags ]
        newTags = { "N:"+tag+"=="+value for tag,value in node.tags.items() if not tag in killTags }
        ntags = newTags | lastTags
        lastTags = newTags

        atags = ctags + list(ntags)

        combined=combinations(atags,depth)

        for ctag in combined :
            if ctag in allTags :
                (l,c) = allTags[ctag]
                if ctag.count("W:")>0 :
                    if ctag.count("N:") > 0 :
                        allTags[ctag] = (l+length,c+1)
                    else :
                        allTags[ctag] = (l+length,0)
                else :
                    allTags[ctag] = (0,c+1)
            else :  
                if ctag.count("W:")>0 :
                    if ctag.count("N:") > 0 :
                        allTags[ctag] = (length,1)
                    else :
                        allTags[ctag] = (length,0)
                else :
                    allTags[ctag] = (0,1)

    return allTags

def addRule(currentRules,rule,points,reason) :
    """Helper function to add a new rule to a rule list, adding also null parent rules if needed"""
    log("Adding rule",rule,points,reason,prio=6)
    currentRules[rule]=points
    parts = rule.rsplit(" && ",1)
    if len(parts)>1 and not parts[0] in currentRules :
        addRule(currentRules,parts[0],(0,0),"")

training=[]

# Some training rules for pedestrian routing
# Each node contains start-node-id, end-node-id, vector of node-ids the correct route should hit and a description of the rule
training+=[(322724138 ,1453882690,[1453886768],           "Unterführung Seckenheimer Landstraße")]
training+=[(1756299817,502884638 ,[502884643, 1756563796],"Ampeln und Kreisel Seckenheimer Landstraße")]
training+=[(413010379 ,310400601 ,[535605593],            "Fußweg")]
training+=[(1881726485,142350530 ,[527915767],            "Fußweg statt Gleise oder Straße")]
training+=[(1468332673,1113318377,[1113317863],           "Unterführung" )]
training+=[(2121135484,3842351078, [3842351076],            "Ampeln Dudenstraße Käfertaler Straße")]
training+=[(1677760912,1612259391, [3842501028,1834049546],"Käfertaler Straße Nord")]
training+=[(1677760912,3682702873, [3307348383],           "Käfertaler Straße Süd")]
training+=[(1173745024,3542320641, [1173732262,299217480], "Unterquerung Feudenheimer Straße")]
training+=[(1098478180,1732901428, [1379282824,1732901432,1002344349,2572058787], "Fuß- und Radweg nutzen")]
training+=[(1448650716,1844687205, [1448650682,1448650693,1362784561,1183431355], "Fuß- und Radweg nutzen 2")]

'''
training+=[(1375039791,1455541494, [1455549916,1455555433,1455541503], "Neustadter Straße West")]
training+=[(322724138,406254680 ,  [322724145,322724999,322725087,956123294,322725090,603138574,603138613,603138704,60312496,406253882], "Seckenheimer Landstraße")]
training+=[(249805903,310205463, [251718412],            "Ruhige Straßen sind besser")]
training+=[(1317464103,2379698798,[1197278190,603237135,673789943], "Von Plattform zu Plattform")]
training+=[(266757865,266756532,  [1454283206,1759419579],"Brücken richtig gehen")]
training+=[(1434504625,2542264822,[1434504109],           "Gatter meiden")]
training+=[(2103526714,1434504539,[2103526666],           "Gatter meiden 2")]
training+=[(1756710506,2429466372,[393849218],            "Wege statt Straßen")]
training+=[(1098478174,1355500437, [1165361256,1422722333],         "Ampel nutzen")]
training+=[(603140003,1098478174, [1791262636],           "Autobahnbrücke richtig nutzen")]
training+=[(1098478180,6069448777, [1362784564],         "Feldweg nutzen, wenn gut")]
training+=[(1860572349,1825708545 ,[1986235290,1986235278,1732872569], "Lauffener Straße")]
training+=[(1422722333,1422743236, [1422722322,1422722338,1422722336], "Ampel über Siebenbürger Straße")]
training+=[(1098478174,1165361290, [1165361330,1165361256], "Ampel über Banater Straße")]
training+=[(249805898,310399252,   [249805900],            "Hauptstraße an Ampel queren")]
training+=[(4437962975,304729644,  [1363816431,1358213268,1358213265], "Fußweg an Pommernstraße")]
training+=[(6556111157,304942679,  [1375188617,2793536573,1375188621], "Überkreuzung Wingertsbuckel")]
training+=[(1178604860,1178604881, [1359858733,1359858737,1178604826,1178604872,1178604855], "Wingertsbuckel entlang")]
training+=[(1375309349,2612335766, [1375306583,1375309366], "Überquerung Klingenberger Straße")]
training+=[(1113318243,304942682,  [1113318338,1362784571,1362784574,1375177620,1375179557], "Überquerung Aubuckel")]
training+=[(1183456771,290518526,  [1183456548,1183456456], "Entlang Wallstadter Straße")]
training+=[(1355500435,1025583268, [1355500447,1355500445,1355500439], "Überkreuzung Ilvesheimer Straße")]
training+=[(1113318243,1178604845, [1362784571],            "Überkreuzung Aubuckel Wingertsbuckel")]
training+=[(2121121480,2121135484, [2121135497,2121135479,2121135504,2121135472,2578451911,2121143103,2121135491], "Entlang Dudenstraße")]
training+=[(253877953,1472399057,  [1874987211,766746541,1165181988], "Entlang Weinheimer Straße")]
training+=[(1836601732,1296616860, [300891440],            "Luisenpark Wege")]
training+=[(3439682575,268325207,  [273179548],            "Luisenpark Wege 2")]
training+=[(2594574429,268325195,  [1836601614],           "Luisenpark Eingang")]
training+=[(1270403687,1270706639, [1744716500],           "Bushaltestelle Pfeifferswörth - Feudenheimer Straße")]
training+=[(474658341,1247437361,  [1751118421],          "Überquerung Ludwig-Ratzel-Straße")]
#training+=[(1751118421,2136553689, [2594575002],          "Entlang Luisenpark")]
training+=[(411758474,1751600352, [1751558496,1751600341],"Seckenheimer Landstraße / Dürerstraße")]
training+=[(766746544,280267372,   [1360957710,304944550,1589652383], "Koblenzer Straße / Im Rott")]
training+=[(30561280,1434504103,   [30561279],             "Keine Parkplatztouren in der Au")]
training+=[(75961572,1338448176,   [144213072],            "Tauberbishofsheimer Straße")]
training+=[(1430383985,1165361104, [297597831],            "Umgehung Banater Straße")]
training+=[(378372649,1831969010,  [266924543,1305153463], "Umgehung Neuostheimer Straße")]
training+=[(3320376846,2434547065, [2434533613,2434547068], "Überkreuzung Friedrichsring")]
training+=[(249805910,1486120496,  [475365845],            "Hauptstraße Zugang Bahnsteig")]
training+=[(77862756,1435446288,   [1435446284,1435446293],"Osterburker Straße Ost")]
training+=[(77862756,1518152602,   [1169045009,1518152595],"Osterburker Straße West")]

#training+=[(840917640,2235009413,[1453886768,1435317906,502884628,266186964,502884623,266191035,30561286,893087192] , "Coblitzallee nach Käfertal nach Google Pedestrian") ]
'''

currentRules = {}
# currentRules = exampleRules

bestRelativeError = 1e+20
bestAbsoluteError = 1e+20

notImprovedCount  = 1

relativeErrorList = []

passed = set()

while True :
    someFail = False
    unchanged = True
    totalRelativeError = 0
    totalAbsoluteError = 0
    worstError = 0
    worstTest = ""
    worstTotal = 0

    for case in training :
        directRoute = case[0:2]
        learnRoute = [ case[0] ] + case[2] + [ case[1] ]

        caseInMap = True
        for node in learnRoute :
            if not node in osmhandler.nodes :
                caseInMap = False
        if not caseInMap :
            log("Skipping test",case[3])
            continue

        log("Running test",case[3])

        
        dictTuple=rulesToDictTuple(currentRules)

        (directCost,directPath) = osmhandler.multiRoute(directRoute,dictTuple)
        (learnCost,learnPath) = osmhandler.multiRoute(learnRoute,dictTuple)

        absoluteError = learnCost - directCost
        relativeError = absoluteError / ( directCost + 1e-4 ) * 100

        if absoluteError > worstError :
            worstError = absoluteError
            worstTest=case[3]
            worstTotal = directCost

        totalRelativeError += relativeError
        totalAbsoluteError += absoluteError

        if relativeError < 1e-8 :
            log("Test",case[3]," passed with",directCost,prio=6)
            #if not case[3] in passed :
            #    passed|={case[3]}
            #    osmhandler.gpxFromNodeList([nodeid for (_,nodeid,_,_) in directPath])
        else : 
            log("Test",case[3],"failed with",directCost,f"by {relativeError:.2f}% ({absoluteError:.8f})",prio=7)
            someFail = True
            
            absoluteError = absoluteError * 1.000001
            
            directTags = tagsFromPath(directPath,3)
            learnTags  = tagsFromPath(learnPath,3)

            directUsedTags   = usedTagsFromPath(directPath,dictTuple)
            learnUsedTags    = usedTagsFromPath(learnPath,dictTuple)

            allKeys = directTags.keys() | learnTags.keys()
            allUsedKeys = directUsedTags.keys() | learnUsedTags.keys()

            differenceTags = dict()
            differenceUsedTags = dict()
            existingTags = dict()
            existingUsedTags = dict()

            norm2 = 0

            for key in allKeys : 
                if key in learnTags :
                    plus = learnTags[key]
                    if key in directTags :
                        minus = directTags[key]
                        value = (plus[0]-minus[0],plus[1]-minus[1])
                    else :
                        value = plus
                else :
                    minus = directTags[key]
                    value = (-minus[0],-minus[1])

                if value!=(0,0) :
                    if not key in currentRules :
                        differenceTags[key] = value
                    else :
                        existingTags[key] = value
                        # norm2 += value[0]*value[0] + value[1]*value[1]

            for key in allUsedKeys : 
                if key in learnUsedTags :
                    plus = learnUsedTags[key]
                    if key in directUsedTags :
                        minus = directUsedTags[key]
                        value = (plus[0]-minus[0],plus[1]-minus[1])
                    else :
                        value = plus
                else :
                    minus = directUsedTags[key]
                    value = (-minus[0],-minus[1])

                if value!=(0,0) :
                    if not key in currentRules :
                        differenceUsedTags[key] = value
                        log(key,"not in currentRules but was used?",allUsedKeys,currentRules)
                        exit(1)
                    else :
                        existingUsedTags[key] = value
                        #log("used",key,value)
                        norm2 += value[0]*value[0] + value[1]*value[1]

            oldFactor = 0
            newFactor = 1

            if norm2>0 :

                if notImprovedCount > 10 :
                    oldFactor = 0.9
                    newFactor = 0.1
                else :
                    oldFactor = 1
                    newFactor = 0
                
                compensateError = absoluteError

                while norm2 > 0 and compensateError > 0 :
                    #log("norm2",norm2)
                    nextNorm2 = norm2
                    nextCompensateError = 0
                    for key in existingUsedTags :  
                        (lenWeight,pointWeight)=currentRules[key]
                        (lenCount,pointCount) = existingUsedTags[key]
                        newLenWeight = lenWeight - compensateError * oldFactor * lenCount / norm2
                        newPointWeight = pointWeight - compensateError * oldFactor * pointCount / norm2
                        if newLenWeight < 0 :
                            nextNorm2 -= lenCount * lenCount
                            existingUsedTags[key] = ( 0 , existingUsedTags[key][1] )
                            nextCompensateError += -newLenWeight * lenCount
                            log("Cannot compensate",key,"wrt len reuse error now",nextCompensateError,"weight",nextNorm2,"from",norm2)
                            newLenWeight = 0
                        if newPointWeight < 0 :
                            nextNorm2 -= pointCount * pointCount
                            existingUsedTags[key] = ( existingUsedTags[key][0] , 0 )
                            nextCompensateError += -newPointWeight * pointCount 
                            newPointWeight = 0                                
                            log("Cannot compensate",key,"wrt point reuse error now",nextCompensateError,"weight",nextNorm2,"from",norm2)
                        if newLenWeight != lenWeight or newPointWeight != pointWeight :
                            if (newLenWeight,newPointWeight)!=(0,0) :
                                log("Changing rule",key,"from",currentRules[key],"to",(newLenWeight,newPointWeight),"because",(lenCount,pointCount))
                                currentRules[key]=(newLenWeight,newPointWeight)
                                unchanged = False
                            else:
                                log("Changing rule",key,"from",currentRules[key],"to",(newLenWeight,newPointWeight),"because",(lenCount,pointCount))
                                currentRules[key]=(newLenWeight,newPointWeight)
                                # log("Removing rule",key,"from",currentRules[key],"because",(lenCount,pointCount))
                                # only permissable when there are no more detailed rules in "override=True" mode
                                # del currentRules[key]
                                unchanged = False

                    compensateError = nextCompensateError                    
                    norm2 = nextNorm2

                if norm2<=0 and compensateError>0 :
                    newFactor += compensateError / absoluteError
                    log("Adding remaining error",compensateError,"to newFactor, now",newFactor)

            if newFactor > 0 :
                if len(differenceTags) == 0 :
                    log("There are no tags to add. Lost compensation:",newFactor*absoluteError)
                else :
                    differenceTagsLengthSorted = sorted(differenceTags.items(), key = lambda v : v[1][0] * ( 1 - v[0].count("&&") / 100.0 ) if v[0].count("W:")>0 else 0 )
                    differenceTagsNodeSorted = sorted(differenceTags.items(), key = lambda v : v[1][1] * ( 1 - v[0].count("&&") / 100.0 ) if v[0].count("N:")>0 else 0 )

                    wayRule = differenceTagsLengthSorted[0]
                    if len(differenceTagsLengthSorted)>2 :
                        log("Way diff: ",differenceTagsLengthSorted[0],differenceTagsLengthSorted[1],differenceTagsLengthSorted[2])

                    nodeRule = differenceTagsNodeSorted[0]
                    if len(differenceTagsNodeSorted)>2 :
                        log("Node diff: ",differenceTagsNodeSorted[0],differenceTagsNodeSorted[1],differenceTagsNodeSorted[2])

                    if nodeRule != wayRule :
                        if wayRule[1][0] < 0 :
                            addRule(currentRules,wayRule[0],( -(absoluteError*newFactor / 2) / wayRule[1][0] , 0 ),"because "+str(wayRule[1]))
                            unchanged = False
                            notImprovedCount = 0
                        else :
                            pass
                            # addRule(currentRules,wayRule[0],(0,0),"because "+str(wayRule[1]))

                        if nodeRule[1][1] < 0 :
                            addRule(currentRules,nodeRule[0],(0,-(absoluteError*newFactor / 2) / nodeRule[1][1] ),"because "+str(nodeRule[1]))
                            unchanged = False
                            notImprovedCount = 0
                        else :
                            pass
                            # addRule(currentRules,nodeRule[0],(0,0),"because "+str(nodeRule[1]))
                    else :
                        if  wayRule[1][0] < 0 and wayRule[1][1] < 0 :
                            addRule(currentRules,wayRule[0],( -(absoluteError*newFactor / 2) / wayRule[1][0] , -(absoluteError*newFactor / 2) / wayRule[1][1] ),"because "+str(wayRule[1]))
                            unchanged = False
                            notImprovedCount = 0
                        elif wayRule[1][0] < 0 :
                            addRule(currentRules,wayRule[0],( -(absoluteError*newFactor ) / wayRule[1][0] , 0 ),"because "+str(wayRule[1]))
                            unchanged = False
                            notImprovedCount = 0
                        elif wayRule[1][1] < 0 :
                            addRule(currentRules,wayRule[0],( 0 , -(absoluteError*newFactor ) / wayRule[1][1] ),"because "+str(wayRule[1]))
                            unchanged = False
                            notImprovedCount = 0
                        else :
                            pass 
                            # addRule(currentRules,wayRule[0],(0,0),"because "+str(wayRule[1]))
                            
            #log(currentRules)
    if totalRelativeError < bestRelativeError : 
        bestRelativeError = totalRelativeError

    if totalAbsoluteError < bestAbsoluteError :
        bestAbsoluteError = totalAbsoluteError
        notImprovedCount = 0
    else :
        notImprovedCount += 1

    if someFail == False or notImprovedCount > 100 :
        log("Fertige Regeln:",currentRules,prio=10)
        ruleList=sorted(currentRules.items())
        for a,b in ruleList:
            if b!=(0,0) or a.count(" && ")>0 :
                log(a,':',b,prio=10)
        break

    relativeErrorList += [(math.log(bestRelativeError),math.log(bestAbsoluteError),math.log(len(currentRules.keys()))) ]

    log("Test:",worstTest,worstTotal,"with error:",worstError,prio=8)
    log("Best relative error:",bestRelativeError," Current relative error:",totalRelativeError," Not improved:",notImprovedCount," Keys:",len(currentRules.keys()),prio=8)
    log("Best absolute error:",bestAbsoluteError," Current absolute error:",totalAbsoluteError," Not improved:",notImprovedCount," Keys:",len(currentRules.keys()),prio=8)
        


log("Improved Routing von Coblitzallee nach Käfertal",prio=10)
(cost,path)=osmhandler.multiRoute([840917640,2235009413],rulesToDictTuple(currentRules))
log("Open",osmhandler.gpxFromNodeList([nodeid for (_,nodeid,_,_) in path]),"in GPX viewer as https://www.j-berkemeier.de/ShowGPX.html",prio=10)

# Display of sum of relative and absolute errors and number of rules over iterations
plt.plot(relativeErrorList)
plt.show()

