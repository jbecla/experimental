#!/usr/bin/python

import argparse
import pprint
import requests

'''
Queries LSST Jira, fetches all database-related epics
and produces html file that contains:
a) a 2-D table (wbs vs fiscal years)
b) a list of orphans epics that did not make it to the 2-D table
It also shows blocking epics. To turn this off, run with "-b 0"
It also show done epics. to turn this off, run with "-d 0"

Author: Jacek Becla / SLAC
'''

wbses = {
    '02C.06.01.01': 'Catalogs Alerts and Metadata',
    '02C.06.01.02': 'Image and File Archive',
    '02C.06.02.01': 'Data Access Client Framework',
    '02C.06.02.02': 'Data Definition Client Framework',
    '02C.06.02.03': 'Query Services',
    '02C.06.02.04': 'Image Service'
}

# fiscal years
fys = ('FY15', 'FY16', 'FY17', 'FY18', 'FY19', 'FY20')
# cycles
cycles = ('S15','W15','S16','W16','S17','W17','S18','W18','S19','W19','S20','W20')

cells = {}
for wbs in wbses:
    cells[wbs] = {}
    for fy in fys:
        cells[wbs][fy] = []

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--showBlockers', required=False, default=1)
parser.add_argument('-d', '--showDone', required=False, default=1)
args = vars(parser.parse_args())
showBlockers = int(args['showBlockers'])
showDone = int(args['showDone'])

SEARCH_URL = "https://jira.lsstcorp.org/rest/api/2/search"

result = requests.get(SEARCH_URL, params={
    "maxResults": 10000,
    "jql":('project = DM'
           ' AND issuetype = Epic'
           ' AND component in (cat, "Data Archive", database, '
           'db, dbserv, metaserv, imgserv, qserv, webserv, XLDB)')
    }).json()

# for keeping issues that won't make it into the WBS + FY structure
orphans = []


class EpicEntry:
    def __init__(self, key, summary, status, blockedBy=None):
        self.key = key
        self.summary = summary
        self.status = status
        self.blockedBy = blockedBy

def genEpicLine(epic):
    if epic.status == "Done":
        (stStart, stStop) = ("<strike>","</strike>")
    else:
        (stStart, stStop) = ("", "")
    return '%s<a href="https://jira.lsstcorp.org/browse/%s">%s</a>%s' % \
        (stStart, epic.key, epic.summary, stStop)


# build quick lookup array (key->status)
lookupArr = {}
for issue in result['issues']:
    theKey = issue['key']
    theSts = issue['fields']['status']['name']
    lookupArr[theKey] = theSts

for issue in result['issues']:
    theKey = issue['key']
    theSmr = issue['fields']['summary']
    theWBS = issue['fields']['customfield_10500']
    theSts = issue['fields']['status']['name']
    theFY  = theSmr[:4]

    # skip 'Done' if requested
    if theSts == 'Done' and not showDone:
        continue

    # Deal with blocking epics
    blkdBy = []
    if showBlockers:
        for iLink in issue['fields']['issuelinks']:
            if iLink['type']['inward']=='is blocked by' and 'inwardIssue' in iLink:
                blkKey = iLink['inwardIssue']['key']
                blkSmr = iLink['inwardIssue']['fields']['summary']
                blkSts = lookupArr[blkKey] if blkKey in lookupArr else None
                blkdBy.append(EpicEntry(blkKey, blkSmr, blkSts))
    # Save in the "cells" array
    if theWBS in wbses and theFY in fys:
        #print "GOOD: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[4:], theSts, blkdBy))
    elif theWBS in wbses and theSmr[:3] in cycles:
        theFY = 'FY%s' % theSmr[1:3]
        #print "GOOD: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)
        cells[theWBS][theFY].append(EpicEntry(theKey, theSmr[3:], theSts, blkdBy))
    else:
        orphans.append(EpicEntry(theKey, theSmr, theSts, blkdBy))
        #print "ORPHAN: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)

theHTML = '''<table border='1'>
  <tr>
    <td></td>'''
for fy in fys:
    theHTML += '''
    <td align='middle'>%s</td>''' % fy
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
    <td valign="top"></td>'''
        else:
            theHTML += '''
    <td valign="top">
      <ul style="list-item-style:none; margin-left:0px;padding-left:20px;">'''
            for epic in cellContent:
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

theHTML += '''
</table>
'''


theHTML += '''
<p>The following did not make it to the above table:
<ul>
'''
for o in orphans:
    theHTML += '''
      <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % \
          (o.key, o.summary)
theHTML += '''
</ul></p>'''

print theHTML
