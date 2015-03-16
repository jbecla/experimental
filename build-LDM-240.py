#!/usr/bin/python

import requests

'''
Queries LSST Jira, fetches all "todo" database-related epics
and produces html file that contains:
a) a 2-D table (wbs vs fiscal years)
b) a list of orphans epics that did not make it to the 2-D table

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

SEARCH_URL = "https://jira.lsstcorp.org/rest/api/2/search"

result = requests.get(SEARCH_URL, params={
    "maxResults": 10000,
    "jql":('project = DM'
           ' AND issuetype = Epic'
           ' AND status = "To Do"'
           ' AND component in (cat, "Data Archive", database, '
           'db, dbserv, metaserv, imgserv, qserv, webserv, XLDB)')
    }).json()

# for keeping issues that won't make it into the WBS + FY structure
orphans = []

for issue in result['issues']:
    theKey = issue['key']
    theSmr = issue['fields']['summary']
    theWBS = issue['fields']['customfield_10500']
    theFY  = theSmr[:4]
    if theWBS in wbses and theFY in fys:
        #print "GOOD: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)
        cells[theWBS][theFY].append([theKey, theSmr[4:]])
    elif theWBS in wbses and theSmr[:3] in cycles:
        theFY = 'FY%s' % theSmr[1:3]
        #print "GOOD: %s, %s, %s, %s" % (theKey, theWBS, theFY, theSmr)
        cells[theWBS][theFY].append([theKey, theSmr[3:]])
    else:
        orphans.append([theKey, theSmr])
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
    <td>%s<br>%s</td>''' % (row, wbses[row])
    for col in cells[row]:
        cellContents = cells[row][col]
        if len(cellContents) == 0:
            theHTML += '''
    <td></td>'''
        else:
            theHTML += '''
    <td><ul>'''
            for item in cellContents:
                theHTML += '''
                <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % \
                    (item[0], item[1])
            theHTML += '''
    </ul></td>'''
    theHTML += '''
  </tr>'''

theHTML += '''
</table>

<p>The following did not make it to the above table:
<ul>
'''
for o in orphans:
    theHTML += '''
      <li><a href="https://jira.lsstcorp.org/browse/%s">%s</a></li>''' % \
          (o[0], o[1])
theHTML += '''
</ul></p>'''

print theHTML
