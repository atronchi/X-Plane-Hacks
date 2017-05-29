from bs4 import BeautifulSoup as bs
import re
import requests
import urllib
from datetime import datetime
from pytz import timezone


url = 'https://pilotweb.nas.faa.gov/PilotWeb/flightPathSearchAction.do'

#form =a

#form_data = {k: v for k,v in [fm.split('=') for fm in urllib.unquote('formatType=DOMESTIC&geoFlightPathIcao1=KSQL&geoFlightPathIcao2=KMRY&geoFlightPathIcao3=&geoFlightPathIcao4=&geoFlightPathIcao5=&geoFlightPathbuffer=20&geoFlightPathEnrouteOption=ENROUTEAIRPORTSANDNAVAIDS&geoFlightPathRegulatoryOption=REGULATORYNOTICES&openItems=icaosHeader%2Cicaos%3AicaoHead%2Cicao%3AflightPathHeader%2CflightPath%3ArightNavSec0%2CrightNavSecBorder0%3A&actionType=flightPathSearch').split('&')]}

form_data = {
 'actionType': 'flightPathSearch',
 'formatType': 'DOMESTIC',
 'geoFlightPathEnrouteOption': 'ENROUTEAIRPORTSANDNAVAIDS',
 'geoFlightPathIcao1': 'KSQL',
 'geoFlightPathIcao2': 'KMRY',
 'geoFlightPathIcao3': '',
 'geoFlightPathIcao4': '',
 'geoFlightPathIcao5': '',
 'geoFlightPathRegulatoryOption': 'REGULATORYNOTICES',
 'geoFlightPathbuffer': '20',
 'openItems': 'icaosHeader,icaos:icaoHead,icao:flightPathHeader,flightPath:rightNavSec0,rightNavSecBorder0:'
}


r = requests.post(url, data=f)
soup = bs(r.text)

class Notam(object):
    def parse(self, pat, g, fmt=None):
        m = re.match(pat, self.raw)
        if m:
            if isinstance(g, int):
                return fmt(m.group(g)) if fmt else m.group(g)
            if isinstance(g, (list, tuple)):
                return [fmt(M) if fmt else M for M in m.group(*g)]
        else:
            return None

    def __init__(self, n):
        self.raw = n

        self.type = self.parse('^!([A-Z]*)\s.*', 1)

        self.loc_raw = self.parse('.*\s+(\d+)N(\d+)W\s+.*', (1,2))  # lat N, lon E in deg
        self.latlon = [float(l)/10000 for l in self.loc_raw] if self.loc_raw else None
        self.loc2 = self.parse('.*\s+\d+N\d+W\s+\((.*?)\).*', 1)  # human readable location

        self.alt_ft = self.parse('.*\s+(\d+)FT\s+.*', 1, fmt=int)  # obstruction altitude in FT
        self.alt_ft_agl = self.parse('.*\s\(+(\d+)FT AGL\)\s+.*', 1, fmt=int)  # obstruction altitude in FT AGL

        self.time_raw = self.parse('.*\s(\d+)-(\d+)([A-Z]*)$', (1,2,3))  # time valid from, to, timezone
        self.time = [datetime(
                *[int(t[i:i+2]) for i in range(0, len(t), 2)], 
                tzinfo=timezone(self.time_raw[2] or 'UTC')
            ) for t in self.time_raw[:2]
        ] if self.time_raw else None

    def __repr__(self):
        return self.raw

notams = [Notam(n.get_text().strip()) for n in soup.div(attrs={'id': 'notamRight'})]

n = notams[0]

