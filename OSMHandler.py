import osmium as osm
import math
import heapq

class Node:
    def __init__(self,id,lat,lon,tags) :
        self.id   = id
        self.lat  = lat
        self.lon  = lon
        self.tags = tags
        self.ways = dict()

    def __str__(self) :
        if "name" in self.tags :
            return "Node "+str(self.id)+" "+self.tags["name"]+" ("+str(self.lat)+","+str(self.lon)+")"
        else :
            return "Node "+str(self.id)+" ("+str(self.lat)+","+str(self.lon)+")"

    def url(self) :
        return "https://www.openstreetmap.org/node/" + str(self.id)

class Way:
    def __init__(self,id,nodes,tags) :
        self.id    = id
        self.nodes = nodes
        self.tags  = tags
    
    def __str__(self) :
        if "name" in self.tags :
            return "Way "+str(self.id)+" "+self.tags["name"]+" "+str(self.nodes)
        else :
            return "Way "+str(self.id)+" "+str(self.nodes)

    def url(self) :
        return "https://www.openstreetmap.org/way/" + str(self.id)


class OSMHandler(osm.SimpleHandler) :
    def __init__(self,override):
        osm.SimpleHandler.__init__(self)
        self.nodes = dict()
        self.ways = dict()
        self.override = override

    def node(self, n):
        self.nodes[n.id] = Node(n.id,
                                n.location.lat,
                                n.location.lon,
                                { key : value for (key,value) in n.tags } )

    def way(self, w):
        if "highway" in w.tags :
            self.ways[w.id] = Way(w.id,
                                    [ node.ref for node in w.nodes ],
                                    { key : value for (key,value) in w.tags } )

            if not "sidewalk" in w.tags :
                self.ways[w.id].tags["sidewalk"]="unknown"

            if len(w.nodes)==1 :
                self.nodes[w.nodes[0].ref].ways[w.id] = []
            else :
                self.nodes[w.nodes[0].ref].ways[w.id] = [w.nodes[1].ref]
                for i in range(1,len(w.nodes)-1) : 
                    self.nodes[w.nodes[i].ref].ways[w.id] = [w.nodes[i-1].ref,w.nodes[i+1].ref]
                self.nodes[w.nodes[len(w.nodes)-1].ref].ways[w.id] = [w.nodes[len(w.nodes)-2].ref]

    def relation(self, r):
        pass

    def distance(self,node1,node2) :
        theta = node1.lon - node2.lon
        dist = math.sin(math.radians(node1.lat)) * math.sin(math.radians(node2.lat)) + math.cos(math.radians(node1.lat)) * math.cos(math.radians(node2.lat)) * math.cos(math.radians(theta))
        dist = math.degrees(math.acos(min(dist,1)))
        dist = dist * 60 * 1.1515
        dist = dist * 1.609344 * 1000
        return dist

    def penalty(self,dictTupleRules,lastnode,nextnode,way) :
        lengthPenalty = 0
        pointPenalty  = 0
        penaltyCount  = 0

        for t in range(3) :
            if t == 0 :
                obj = lastnode
                r = 0
            elif t == 1 : 
                obj = nextnode
                r = 0
            else :
                obj = way
                r = 1

            for tag,value in obj.tags.items() :
                item = tag + "==" + value
                #log(t,r,item)
                if item in dictTupleRules[r] :
                    #log("found: ",item,dictTupleRules[r][item])
                    (lp,pp) = dictTupleRules[r][item][0]
                    (lpa,ppa,subCount) = self.penalty(dictTupleRules[r][item][1],lastnode,nextnode,way)

                    penaltyCount += subCount

                    if self.override :
                        if subCount > 0 :
                            lengthPenalty += lpa
                            pointPenalty  += ppa # or multiply everything?
                        else :
                            penaltyCount  += 1

                            lengthPenalty += lp
                            pointPenalty  += pp # or multiply everything?
                    else :
                        penaltyCount += 1

                        lengthPenalty += lp + lpa
                        pointPenalty  += pp + ppa # or multiply everything?

        return (lengthPenalty,pointPenalty,penaltyCount)

    def penaltyRules(self,dictTupleRules,lastnode,nextnode,way) :

        rules = dict()
        
        for t in range(3) :
            if t == 0 :
                obj = lastnode
                r = 0
                p = "N:"
            elif t == 1 : 
                obj = nextnode
                r = 0
                p = "N:"
            else :
                obj = way
                r = 1
                p = "W:"

            for tag,value in obj.tags.items() :
                item = tag + "==" + value
                #log(t,r,item)
                if item in dictTupleRules[r] :
                    #log("found: ",item,dictTupleRules[r][item])
                    (lp,pp) = dictTupleRules[r][item][0]
                    subRules = self.penaltyRules(dictTupleRules[r][item][1],lastnode,nextnode,way)
                    
                    if self.override :
                        if len(subRules) > 0 :
                            for subitem in subRules :
                                rules[p+item+" && "+subitem] = subRules[subitem]
                        else :
                            rules[p+item]=(lp,pp)
                    else :
                        for subitem in subRules :
                            rules[p+item+" && "+subitem] = subRules[subitem]
                        rules[p+item] =(lp,pp)

        return rules


    def multiRoute(self,nids,dictTupleRules=(dict(),dict())) :
        totalCost = 0
        totalPath = []

        for i in range(len(nids)-1) :
            (cost,path) = self.route(nids[i],nids[i+1],dictTupleRules)
            totalCost += cost
            totalPath += path

        return (totalCost,totalPath)

    def route(self,nid1,nid2,dictTupleRules=(dict(),dict())) :
        node1 = self.nodes[nid1]
        node2 = self.nodes[nid2]

        openList = []
        closedList = dict() # for hashed access
        openListData = dict()
        
        heapq.heappush(openList,(0,nid1))
        openListData[nid1] = (0,[ (list(node1.ways.keys())[0],nid1,0,0) ])

        while len(openList)>0 :
            currentValue,currentId = heapq.heappop(openList)

            if currentId in closedList : # As long obsolete routes are not removed due to heapq implementation
                continue

            currentCost,currentPath = openListData.pop(currentId)

            # nextPath = currentPath + [currentId]

            if currentId == nid2 :
                return (currentCost,currentPath)

            closedList[currentId] = True

            currentNode = self.nodes[currentId]

            #log(currentCost,"\t",currentValue,"\t",currentNode)

            for wid , nids in currentNode.ways.items() :
                for nid in nids :
                    if not nid in closedList :
                        way = self.ways[wid]
                        nextNode = self.nodes[nid]
                        segmentLength = self.distance(currentNode,nextNode)

                        (lengthPenalty,pointPenalty,penaltyCount) = self.penalty(dictTupleRules,currentNode,nextNode,way)

                        if lengthPenalty < 0 or pointPenalty < 0 :
                            log("Error: Negative weights! ",lengthPenalty,pointPenalty,prio=10)
                            log(" -> From:",currentNode," To: ",nextNode," Way: ",way,prio=10)
                            exit(1)

                        # max to prevent negativity
                        segmentCost = segmentLength * ( 1 + max( lengthPenalty , 0 ) ) + max( 0 , pointPenalty )

                        nextCost = currentCost + segmentCost

                        if nid in openListData :
                            otherCost , _ = openListData[nid]
                            if otherCost < nextCost :
                                continue
                            # remove obsolete entry from priority queue - not done due to heapq implementation
                        openListData[nid]=(nextCost,currentPath + [ (wid,nid,segmentCost,segmentLength) ] )
                        nextHeuristic = nextCost + self.distance(nextNode,node2)
                        heapq.heappush(openList,(nextHeuristic,nid))
        print("Bad luck")
        return (0,[])

    def gpxFromNodeList(self,nodes,filename=None) :
        if filename==None :
            filename = "route-"+str(nodes[0])+"-"+str(nodes[-1])+".gpx"

        f = open(filename,"w")
        f.write("<?xml version='1.0' encoding='UTF-8'?>")
        f.write("<gpx version='1.1'><trk><trkseg>")
        for nid in nodes :
            node = self.nodes[nid]
            f.write("<trkpt lat='"+str(node.lat)+"' lon='"+str(node.lon)+"'/>")
        f.write("</trkseg></trk></gpx>")
        f.close()
        return filename
