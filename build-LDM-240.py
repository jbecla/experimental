#!/usr/bin/python

import argparse
from collections import OrderedDict
import math
import pickle
import pprint
import requests

'''
Queries LSST Jira, fetches all database-related epics
and produces html file that contains:
a) a 2-D table (wbs vs fiscal years)
b) a list of orphans epics that did not make it to the 2-D table
It also shows blocking epics. To turn this off, run with "-b 0"
It also show done epics. to turn this off, run with "-d 0"

For long term planning, uncomment lines starting with PLANNING,
run like this:
./build-LDM-240.py  -b 0 |grep PLANNING|sort > /tmp/x.csv
and open the x.csv with spreadsheet

Author: Jacek Becla / SLAC
'''

wbses = OrderedDict()
wbses['02C.06.01.01'] = 'Catalogs, Alerts and Metadata'
wbses['02C.06.01.02'] = 'Image and File Archive'
wbses['02C.06.02.01'] = 'Data Access Client Framework'
wbses['02C.06.02.02'] = 'Web Services'
wbses['02C.06.02.03'] = 'Query Services'
wbses['02C.06.02.04'] = 'Image and File Services'
wbses['02C.06.02.05'] = 'Catalog Services'

# fiscal years
fys = ('FY15', 'FY16', 'FY17', 'FY18', 'FY19', 'FY20')
# cycles
cycles = ('S15','W15','S16','W16','S17','W17','S18','W18','S19','W19','S20','W20')

cells = OrderedDict()
for wbs in wbses:
    cells[wbs] = {}
    for fy in fys:
        cells[wbs][fy] = []

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--showBlockers', required=False, default=1)
parser.add_argument('-d', '--showDone', required=False, default=1)
parser.add_argument('-o', '--outFileName', required=False, default="/dev/null")

args = vars(parser.parse_args())
showBlockers = int(args['showBlockers'])
showDone = int(args['showDone'])
outFileName = args['outFileName']

SEARCH_URL = "https://jira.lsstcorp.org/rest/api/2/search"

# This is for offline analysis. Run it first with "dumpToFile"
# set to True, this will fetch data from jira as it normally
# does, and save it in file. Then to run offline analysis,
# set readFromFile to True, while dumpToFile is False
fileForOfflineAnalysisDM = "/tmp/for_ldm-240.DM.out"
fileForOfflineAnalysisDLP = "/tmp/for_ldm-240.DLP.out"
dumpToFile = False
readFromFile = False

if readFromFile:
    f = open(fileForOfflineAnalysisDM, "r")
    result = pickle.load(f)
    f.close()
    f = open(fileForOfflineAnalysisDLP, "r")
    resultDLP = pickle.load(f)
    f.close()
else:
    result = requests.get(SEARCH_URL, params={
        "maxResults": 10000,
        "jql":('project = DM'
               ' AND issuetype = Epic'
               ' AND Team = "Data Access and Database"')}).json()

    resultDLP = requests.get(SEARCH_URL, params={
        "maxResults": 10000,
        "jql":('project = "DM Long-range  Planning"'
               ' AND wbs ~ "02C.06*"'
               ' AND type = milestone')}).json()


if dumpToFile:
    f = open(fileForOfflineAnalysisDM, "w")
    pickle.dump(result, f)
    f.close()
    f = open(fileForOfflineAnalysisDLP, "w")
    pickle.dump(resultDLP, f)
    f.close()



# for keeping issues that won't make it into the WBS + FY structure
orphans = []


class EpicEntry:
    def __init__(self, key, summary, status, cycle, sps, blockedBy=None):
        self.key = key
        self.summary = summary
        self.status = status
        self.blockedBy = blockedBy
        self.cycle = cycle
        self.sps = sps

class DLPEpicEntry:
    def __init__(self, key, summary):
        self.key = key
        self.summary = summary

def genEpicLine(epic):
    if epic.cycle == 'W':
        color = "c8682c" # dark orange (for Winter cycle)
    elif epic.cycle == 'S':
        color = "309124" # green (for Summer cycle)
    else:
        color = "2c73c8" # blue (cycle no specified)
    if epic.status == "Done":
        (stStart, stStop) = ("<strike>","</strike>")
    else:
        (stStart, stStop) = ("", "")

    fteMonth = epic.sps/26.3
    if fteMonth % 1 < 0.05:
        fteMonth = "%d" % fteMonth
    else:
        fteMonth = "%.1f" % fteMonth
    return '%s<a href="https://jira.lsstcorp.org/browse/%s"><font color="%s">%s (%s)</font></a>%s' % \
        (stStart, epic.key, color, epic.summary, fteMonth, stStop)


# build quick lookup array (key->status)
lookupArr = {}
for issue in result['issues']:
    theKey = issue['key']
    theSts = issue['fields']['status']['name']
    lookupArr[theKey] = theSts

# count story points per FY
spsArr = {}
for fy in fys:
    spsArr[fy] = 0

dlpMilestonesArr = {}
for fy in fys:
    dlpMilestonesArr[fy] = []

for issue in resultDLP['issues']:
    theKey = issue['key']
    cycle = issue['fields']['fixVersions'][0]['name']
    smr = issue['fields']['summary']
    fy = "FY%s" % cycle[1:]
    dlpMilestonesArr[fy].append(DLPEpicEntry(theKey, smr))

for fy in dlpMilestonesArr:
    s = ""
    for e in dlpMilestonesArr[fy]:
        s += "(%s, %s) " % (e.key, e.summary)
    print "%s: %s" % (fy, s)

for issue in result['issues']:
    theKey = issue['key']
    theSmr = issue['fields']['summary']
    theWBS = issue['fields']['customfield_10500']
    theSts = issue['fields']['status']['name']
    theSPs = issue['fields']['customfield_10202']
    if theSPs is None:
        theSPs = 0
    else:
        theSPs = int(theSPs)
    theFY = theSmr[:4]

    # skip 'Done' if requested
    if theSts == 'Done' and not showDone:
        continue

    # skip 'KPM Measurements'
    if "KPM Measurement" in theSmr:
        continue

    # Deal with blocking epics
    blkdBy = []
    if showBlockers:
        for iLink in issue['fields']['issuelinks']:
            if iLink['type']['inward']=='is blocked by' and 'inwardIssue' in iLink:
                blkKey = iLink['inwardIssue']['key']
                blkSmr = iLink['inwardIssue']['fields']['summary']
                blkSts = lookupArr[blkKey] if blkKey in lookupArr else None
                blkdBy.append(EpicEntry(blkKey, blkSmr, blkSts, 'Y', theSPs))
    # Save in the "cells" array
    if theWBS in wbses and theFY in fys:
        spsArr[theFY] += theSPs
        #print "GOOD: %s, %s, %s, %d, %s" % (theKey, theWBS, theFY, theSPs, theSmr)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[4:], theSts, 'Y', theSPs, blkdBy))
        print "PLANNING;%s;%s;%d;%s" %(theFY, theKey, theSPs, theSmr[4:])
    elif theWBS in wbses and theSmr[:3] in cycles:
        theFY = 'FY%s' % theSmr[1:3]
        spsArr[theFY] += theSPs
        #print "GOOD: %s, %s, %s, %d, %s" % (theKey, theWBS, theFY, theSPs, theSmr)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[3:], theSts, theSmr[:1], theSPs, blkdBy))
        print "PLANNING;%s;%s;%d;%s" %(theFY, theKey, theSPs, theSmr[3:])
    else:
        orphans.append(EpicEntry(theKey, theSmr, theSts, 'Y', theSPs, blkdBy))
        #print "ORPHAN: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)

theHTML = '''

<html>
<head>
<title>LDM-240 for 02C.06</title>
</head>
<body>

<table border='1'>
  <tr>
    <td></td>'''
for fy in fys:
    theHTML += '''
    <td align='middle' width='15%%'>%s</td>''' % fy
theHTML += '''
  </tr>'''

for row in cells:
    theHTML += '''
  <tr>
    <td valign="top">%s<br>%s</td>''' % (row, wbses[row])
    for col in cells[row]:
        cellContent = cells[row][col]
        if len(cellContent) == 0:
            theHTML += '''
    <td valign="top">&nbsp;</td>'''
        else:
            theHTML += '''
    <td valign="top">
      <ul style="list-item-style:none; margin-left:0px;padding-left:20px;">'''
            for cycle in ('W', 'S', 'Y'): # sort epics by cycle
                for epic in cellContent:
                    if epic.cycle == cycle:
                        theHTML += '''
        <li>%s</li>''' % genEpicLine(epic)
                        if len(epic.blockedBy) > 0:
                            theHTML += '''
          <ul>'''
                            for bEpic in epic.blockedBy:
                                theHTML += '''
            <li><small><i>%s</i></small></li>''' % genEpicLine(bEpic)
                            theHTML += '''
          </ul>'''
            theHTML += '''
      </ul></td>'''
    theHTML += '''
  </tr>'''

# now the DLP row with milestones
theHTML += '''
  <tr>
      <td valign="top" bgcolor="#BEBEBE">DLP milestones</td>
'''
for fy in fys:
    theHTML += '''
      <td valign="top" bgcolor="#BEBEBE"><ul style="list-item-style:none; margin-left:0px;padding-left:20px;">
'''
    for e in dlpMilestonesArr[fy]:
        theHTML += '''
        <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>
''' % (e.key, e.summary)
    theHTML += '''
      </ul></td>
'''
theHTML += '''
  </tr>
</table>

<p>Breakdown of story points per FY:
<table border='1'>
<tr><td align='middle'>FY<td align='middle'>story points<td align='middle'>FTE-months<td align='middle'>FTE-years
'''
for fy in fys:
    theHTML += '''
    <tr><td align='middle'>%s<td align='middle'>%d<td align='middle'>%d<td align='middle'>%0.1f
''' % (fy, spsArr[fy], spsArr[fy]/26.3, spsArr[fy]/26.3/12)

theHTML += '''
</table>

<p>The following did not make it to the above table:
<ul>
'''

for o in orphans:
    theHTML += '''
      <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % \
          (o.key, o.summary)
theHTML += '''
</ul></p>
<p>
Explanation: orange color - winter cycle, green color - summer cycle, blue color - cycle not specified.</p>

The numbers next to epics in brackets: effort expressed in FTE-months, where 1 FTE month = 26.3 story points

</body>
</html>
'''

if outFileName != "/dev/null":
    f = open(outFileName, "w")
    f.write(theHTML)
    f.close()
