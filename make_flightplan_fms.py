#!/usr/local/bin/python
#import sys
#with open('/tmp/xplane_printer_file', 'w') as f:
#    f.write(sys.read())

'''
 ** Build a webapp that does these things by running locally with X-Plane (or can connect to a remote X-Plane instance)

 * Provides a webpage to
    - connection via local/VPN/external AWS instance, displays clickable link in X-Plane to open this page locally and/or remotely
    - enable remote instruction
     - configure/provide a flight plan/weather
     - view flight position/progress/status
     - fail instruments, present weather scenarios
     - share screen with instructor
     - provide two-way audio (e.g. for PilotEdge AND student/pilot comms), and student/instructor/pilotedge relative volume controls
     - pass X-Plane GPS info out to remote instructor for foreflight, etc., provide remote connection instructions

 * Provide options for typical setup for starting flight
    - Initialize the cockpit with a received flight plan loaded to GPS and COM/NAV radios configured for departure.
    - Start the plane position at a chosen ramp/parking area for the departure airport.
'''
'''
previously...
Following Instructions/Sending\ Data\ to\ X-Plane.rtfd/TXT.rtf make an X-Plane plugin that 
 * Makes a virtual X-Plane printer that outputs an fms file named with the route and altitudes into the X-Plane folder scraped from flight planning software
    - get file from skyvector navlog pdf/link OR foreflight navlog printed to pdf OR flightaware, etc
    - deduplicate any multiple VORs with the same name by choosing the one closest to other waypoints in flight plan if necessary
    - e.g. make a local printer 
        * System Preferences -> Printers -> + (add printer) -> IP -> Address: 127.0.0.1 / Protocol: IPP / Name: make_Xplane_flight_plan
        * check 'Share this printer on the network.'
        * then in a terminal `lpadmin -p make_Xplane_flight_plan -E -v file:<this_file>`
            ... lpadmin -p make_Xplane_flight_plan -E -v file:make_flightplan_fms.py
            lpadmin: File device URIs have been disabled. To enable, see the FileDevice directive in "/private/etc/cups/cups-files.conf"
            http://stackoverflow.com/questions/34358069/how-to-print-a-pdf-to-a-raw-printer-file-with-cups-in-terminal
            add: `FileDevice Yes` as a newline in /private/etc/cups/cups-files.conf
            restart cups: sudo launchctl stop org.cups.cupsd && sudo launchctl start org.cups.cupsd
'''

import argparse
import math
import re
import signal
import socket
import sys


class Airport(object):
    '''
    $ egrep '(KUDD|KSEE)' Resources/GNS430/navdata/Airports.txt
    A,KSEE,SAN DIEGO/EL CAJON/G,32.82622,-116.97244,388,18000,18000,5300
    A,KUDD,PALM SPRINGS/BERMUDA,33.74844,-116.27481,73,18000,18000,5000
    '''
    def __init__(self):
        self.fnam = 'Resources/GNS430/navdata/Airports.txt'
        with open(self.fnam) as f:
            self.header = f.readline().strip()

            self.index = {}
            ln = f.readline()
            while ln:
                if not ln.startswith('A,'): 
                    ln = f.readline()
                    continue

                _, apt_id, apt_desc, lat, lon, _, _, _, alt = ln.strip().split(',')

                if self.index.get(apt_id) is None:
                    self.index[apt_id] = [(apt_id, alt, lat, lon)]
                else:
                    self.index[apt_id].append((apt_id, alt, lat, lon))

                ln = f.readline()

    def get_fms_waypoint(self, apt_id):
        if apt_id in self.index:
            return ['1 {} {} {} {}'.format(*k) for k in self.index[apt_id]]
        else:
            return []

#a = Airport()

class NavAid(object):
    '''
    $ egrep -i '^(TRM|JLI),' Resources/GNS430/navdata/Navaids.txt
    JLI,JULIAN,114.000,1,1,195,33.14046,-116.58594,5560,K2,0
    TRM,THERMAL,116.200,1,1,195,33.62810,-116.16020,-87,K2,0
    TRM,TRES MARIAS,114.700,0,1,195,-18.20324,-45.45707,3055,SB,0
    TRM,LAJES,116.200,0,1,195,38.76025,-27.09144,200,LP,0
    '''
    def __init__(self):
        self.fnam = 'Resources/GNS430/navdata/Navaids.txt'
        with open(self.fnam) as f:
            self.header = f.readline().strip()

            self.index = {}
            ln = f.readline()
            while ln:
                nav_id, nav_desc, freq, _, _, _, lat, lon, alt, _, _ = ln.strip().split(',')

                if self.index.get(nav_id) is None:
                    self.index[nav_id] = [(nav_id, alt, lat, lon)]
                else:
                    self.index[nav_id].append((nav_id, alt, lat, lon))

                ln = f.readline()

    def get_fms_waypoint(self, nav_id):
        # just pretend they're all VOR's (type=3) for now...
        if nav_id in self.index:
            return ['3 {} {} {} {}'.format(*k) for k in self.index[nav_id]]
        else:
            return []

#n = NavAid()

class Waypoint(object):
    '''
    $ egrep -i '(WARNE|CANNO)' Resources/GNS430/navdata/Waypoints.txt
    CANNO,32.77322,-116.62396,K2
    WARNE,33.35256,-116.40151,K2
    '''
    def __init__(self):
        self.fnam = 'Resources/GNS430/navdata/Waypoints.txt'
        with open(self.fnam) as f:
            self.header = f.readline().strip()

            self.index = {}
            ln = f.readline()
            while ln:
                wpt_id, lat, lon, _ = ln.strip().split(',')

                if self.index.get(wpt_id) is None:
                    self.index[wpt_id] = [(wpt_id, 0, lat, lon)]
                else:
                    self.index[wpt_id].append((wpt_id, 0, lat, lon))

                ln = f.readline()

    def get_fms_waypoint(self, wpt_id):
        if wpt_id in self.index:
            return ['11 {} {} {} {}'.format(*k) for k in self.index[wpt_id]]
        else:
            return []

#w = Waypoint()

class Airway(object):
    '''
    $ less Resources/GNS430/navdata/ATS.txt  # Airways
    A,V514,16
    S,MZB,32.78220,-117.22541,HAILE,32.77936,-117.01436,0,79,10.60
    S,HAILE,32.77936,-117.01436,RYAHH,32.77711,-116.86127,79,79,7.70
    S,RYAHH,32.77711,-116.86127,BARET,32.77411,-116.67746,79,80,9.30
    S,BARET,32.77411,-116.67746,CANNO,32.77322,-116.62396,80,353,2.70
    S,CANNO,32.77322,-116.62396,JLI,33.14046,-116.58594,80,24,22.00
    S,JLI,33.14046,-116.58594,WARNE,33.35256,-116.40151,353,24,15.70
    S,WARNE,33.35256,-116.40151,TRM,33.62810,-116.16020,24,22,20.40
    S,TRM,33.62810,-116.16020,CONES,33.80474,-116.01844,25,22,12.70
    S,CONES,33.80474,-116.01844,CLOWD,33.90280,-115.93941,22,22,7.00
    S,CLOWD,33.90280,-115.93941,TNP,34.11223,-115.76991,22,31,15.10
    S,TNP,34.11223,-115.76991,JOTNU,34.32586,-115.52953,22,8,17.50
    S,JOTNU,34.32586,-115.52953,ZELMA,34.78333,-115.32986,32,8,29.10
    S,ZELMA,34.78333,-115.32986,GFS,35.13114,-115.17644,8,21,22.10
    S,GFS,35.13114,-115.17644,SHUSS,35.49553,-114.88784,8,21,26.00
    S,SHUSS,35.49553,-114.88784,LYNSY,35.66054,-114.75615,21,334,11.80
    S,LYNSY,35.66054,-114.75615,BLD,35.99579,-114.86358,21,0,20.70
    '''
    def __init__(self):
        self.fnam = 'Resources/GNS430/navdata/ATS.txt'
        with open(self.fnam) as f:
            self.index = {}
            ln = f.readline()
            while ln:
                _, awy_id, _ = ln.strip().split(',')
                ln = f.readline()

                if awy_id in self.index:
                    while ln and not ln.startswith('A,'):
                        ln = f.readline()
                else:
                    waypoints = []
                    l = ln.split(',')
                    wpt, lat, lon = l[1], l[2], l[3]
                    waypoints.append((wpt, lat, lon))
                    while ln and not ln.startswith('A,'):
                        # edges start with S, and list the waypoints at both ends
                        l = ln.split(',')
                        wpt, lat, lon = l[4], l[5], l[6]
                        waypoints.append((wpt, lat, lon))

                        ln = f.readline()

                    self.index[awy_id] = waypoints


    def get_fms_waypoints_from_a_to_b(self, awy_id, wpt1, wpt2):
        '''Returns waypoints along airway awy_id from waypoint wpt1 to waypoint wpt2, excluding wpt1 and wpt2.'''
        if awy_id not in self.index: return []

        wpts = [w[0] for w in self.index[awy_id]]

        try:
            iw1 = wpts.index(wpt1)
            iw2 = wpts.index(wpt2)
        except:
            raise Exception('{} or {} is not along {}'.format(wpt1, wpt2, awy_id))

        if iw1 > iw2:
            return ['11 {} 0 {} {}'.format(*k) for k in self.index[awy_id][iw1-1:iw2:-1]]
        else:
            return ['11 {} 0 {} {}'.format(*k) for k in self.index[awy_id][iw1+1:iw2]]

#aw = Airway()

def make_fms(plan_str):
    """ https://flightplandatabase.com/dev/specification
    e.g.
    plan_str: 'KUDD TRM V514 BARET KSEE'

    Returns: file as follows
I
3 version
1 
4 
1 EDDM 0.000000 48.364822 11.794361 
2 GL 1000 57.083820 9.680093 
3 KFK 2000 38.803889 30.546944
11 DETKO 0.600000 28.097222 49.525000 
28 +13.691_+100.760 0.000000 13.691230 100.760811
|  ^id              ^alt     ^lat      ^lon 
^ type

types:
    1 - Airport ICAO 
    2 - NDB 
    3 - VOR 
    11 - Fix 
    28 - Lat/Lon Position
altitude in ft
lat/lon in decimal, up to 6 places
"""
    a = Airport()
    n = NavAid()
    wp = Waypoint()
    aw = Airway()

    plan = plan_str.split()
    candidate_waypoints = []
    for i,p in enumerate(plan):
        if i == 0 or i == len(plan) - 1:
            # end points cannot be airways
            wpts = a.get_fms_waypoint(p) + n.get_fms_waypoint(p) + wp.get_fms_waypoint(p)

            if len(wpts) == 0: 
                raise Exception('{} is neither a known airport, navaid, or waypoint.'.format(p))
            else:
                candidate_waypoints.append((p, 'waypoint', wpts))
        else:
            wpts = a.get_fms_waypoint(p) + n.get_fms_waypoint(p) + wp.get_fms_waypoint(p)

            if len(wpts) == 0: 
                wpts = aw.get_fms_waypoints_from_a_to_b(p, plan[i-1], plan[i+1])
                
                if len(wpts) == 0:
                    raise Exception('{} is neither a known airport, navaid, waypoint, or airway.'.format(p))
                else:
                    candidate_waypoints.append((p, 'airway', wpts))
            else:
                candidate_waypoints.append((p, 'waypoint', wpts))

    print candidate_waypoints
    waypoints = []
    for p in candidate_waypoints:
        if len(p[2]) == 1:
            waypoints.append(p[2][0])
        elif p[1] == 'airway':
            waypoints += p[2]
        else:  # p[1] == 'waypoint', but multiple with the same name. Use closest to last waypoint.
            w = p[2]
            y = waypoints[-1].split()
            w.sort(key=lambda x: math.sqrt(
                (float(x.split()[3]) - float(y[3]))**2 + (float(x.split()[4]) - float(y[4]))**2
            ))
            waypoints.append(w[0])
    print waypoints

    fms = 'A\n3 version\n1\n{}\n'.format(len(waypoints)-1) + '\n'.join(waypoints)

    print fms
    fms_fnam = 'Output/FMS Plans/{}.fms'.format(plan_str)
    with open(fms_fnam , 'w') as f:
        f.writelines(fms + '\n')
        f.flush()
    print '\nWrote "{}"'.format(fms_fnam)
    


class AirportENav(object):
    '''
    $ less Resources/default\ scenery/default\ apt\ dat/Earth\ nav\ data/apt.dat
    ...
    1      5 1 0 KSQL San Carlos
    1302 city San Carlos
    1302 country United States
    1302 datum_lat 37.511855556
    1302 datum_lon -122.249522222
    1302 faa_code SQL
    ...
    51 11900 San Carlos CTAF
    53 12160 San Carlos Ground
    54 11900 San Carlos Tower
    55 13395 Norcal Approach
    56 13565 Norcal Departure
    '''

    def readblock(self, f):
        block = {'data': []}
        block['start'] = f.tell()

        ln = f.readline()
        while ln and ln != '\n':
            block['data'].append(ln)
            ln = f.readline()

        block['size'] = f.tell() - block['start']

        return block

    def __init__(self):
        self.fnam = 'Resources/default scenery/default apt dat/Earth nav data/apt.dat'

        # Build an index of the file to enable fast seeking for airports.
        with open(self.fnam, 'r') as f:
            self.header = self.readblock(f)
            self.index = {}

            a = self.readblock(f)
            while a['size'] != 0:
                apt = re.split('\s+', a['data'][0])
                apt_id = apt[4]
                a['data'] = (a['data'][0])

                if self.index.get(apt_id) is None:
                    self.index[apt_id] = a
                else:
                    self.index[apt_id + '_' + str(hash(a['data']))] = a

                #print 'loaded {} from {} to {}'.format(apt_id, a['start'], a['end'])
                a = self.readblock(f)

    def get_raw(self, apt_id):
        if apt_id in self.index:
            with open(self.fnam, 'r') as f:
                f.seek(self.index[apt_id]['start'])
                raw = f.read(self.index[apt_id]['size'])
            return raw
        else: raise Exception('Airport with identifier {} not found in db.'.format(apt_id))

    def show(self, apt_id):
        apt = self.get_raw(apt_id).split('\n')
        for ln in apt:
            splt = re.split('\s+', ln)
            try:
                code = int(splt[0])

                if code in [
                        1,  # header
                        1302,  # location/id metadata
                        100,  # runways
                        21,  # approach lighting
                        #20,  # ground lighting (taxiways, etc)
                        #14,  # tower viewpoint
                        15,  # parking areas
                        #18,  # beacon
                        #19,  # windsocks
                        ] + range(50,60):  # radio frequencies
                    print ln
            except:
                pass

#a = Airport()

class NavAidENav(object):
    '''
    $ less Resources/default\ data/earth_nav.dat
    ...
    3  37.39250000 -122.28130556   2270 11390  40   17.0 OSI  WOODSIDE VORTAC
    '''

    def __init__(self):
        self.fnam = 'Resources/default data/earth_nav.dat'
        self.index = {}

        with open(self.fnam, 'r') as f:
            self.header = f.readline() + '\n' + f.readline() + f.readline()

            ln = f.readline()
            while ln and ln != '99\r\n':
                l = re.split('\s+', ln)

                try:
                    l = [int(l[0]), float(l[1]), float(l[2]), int(l[3]), int(l[4]), int(l[5]), float(l[6]), l[7], ' '.join(l[8:]).strip()]
                except:
                    l = [int(l[0]), float(l[1]), float(l[2]), int(l[3]), int(l[4]), int(l[5]), None, l[6], ' '.join(l[7:]).strip()]

                nav_id = l[7]
                if nav_id in self.index:
                    self.index[nav_id + '_' + str(hash(ln))] = l
                else:
                    self.index[nav_id] = l

                ln = f.readline()

    def get_raw(self, nav_id):
        return [self.index[k] for k in self.index if k.startswith(nav_id)]

    def get_fms(self, nav_id):
        pass

#n = NavAid()


def main(args):
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind the socket to the port
    server_address = ('localhost', 49000)
    beacon_multicast_group = ('239.255.1.1', 49707)

    # Send flight plan to X-Plane


    # Request data from X-Plane

'''
import socket
import struct

MCAST_GRP = '239.255.1.1'
MCAST_PORT = 49707

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
sock.bind((MCAST_GRP, MCAST_PORT))  # use MCAST_GRP instead of '' to listen only to MCAST_GRP, not all groups on MCAST_PORT
mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)

sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

while True:
  print sock.recv(10240)
  # repeatedly prints "BECNhnfml-atronchinjamesE2H" (i.e. "BECNh{this_hosts_name}") when X-Plane is running.
'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Build an FMS file from a text flight plan.')
    parser.add_argument('plan', help='text flight plan, e.g. "KUDD TRM V514 BARET KSEE"')
    parser.add_argument('-l', '--load_plan', help='load the flight plan to X-Plane GPS', action='store_true')
    parser.add_argument('-w', '--watch', help='watch flight progress from X-Plane', action='store_true')

    args = parser.parse_args()

    #signal.signal(signal.SIGINT, exit_handler)

    main(args)

