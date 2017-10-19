from PyQt4 import QtCore, QtGui, Qt, QtNetwork, QtWebKit
from PyQt4.uic import loadUiType
import sys
import struct
import time
import requests
import os
from collections import OrderedDict
import zmq

dirpath = os.path.dirname(__file__)
Ui_MainWindow, QMainWindow = loadUiType(os.path.join(dirpath,'main_window.ui'))

modules = [ {'ip':'192.168.0.51',
             'port':12051,
             'channels':('MC RuO2','','Still'),
             'POE_port':8,
             'isalive':True},
            {'ip':'192.168.0.53',
             'port':12053,
             'channels':('MC Cernox','4K stage','50K stage'),
             'POE_port':6,
             'isalive':True},
          ]

import telnetlib

def resetport(port_number):
    tn = telnetlib.Telnet('192.168.0.1',timeout=5)
    tn.read_until("User:",timeout=5)
    tn.write('admin\r\n')
    tn.read_until("Password:",timeout=5)
    tn.write('cryo\r\n')
    tn.read_until("TL-SG2210P>",timeout=5)
    tn.write('\r\n')
    tn.read_until("TL-SG2210P>",timeout=5)    
    tn.write('enable\r\n')
    tn.read_until("TL-SG2210P#",timeout=5)
    tn.write('configure\r\n')
    tn.read_until("TL-SG2210P(config)#",timeout=5)    
    tn.write('interface gigabitEthernet 1/0/{0}\r\n'.format(port_number))
    tn.read_until("TL-SG2210P(config-if)#",timeout=5)    
    tn.write('power inline supply disable\r\n')
    tn.read_until("TL-SG2210P(config-if)#",timeout=5)    
    time.sleep(2)
    tn.write('power inline supply enable\r\n')    
    tn.read_until("TL-SG2210P(config-if)#,timeout=5")    
    tn.write("exit\r\n")
    tn.close()

class ZMQserver(QtCore.QThread):
    def __init__(self, reply_fun, parent=None, port="5556"):
        super(QtCore.QThread, self).__init__(parent)
        self.port = port
        self.reply_fun = reply_fun
    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind("tcp://*:%s" % self.port)
        while True:
            msg = socket.recv()
            try:
                msg = msg.strip()                
                answer = self.reply_fun(msg)
                answer = str(answer)
            except:
                answer = 'Error'
            socket.send(answer)        

          
class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        # Create the main window
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # Timer to update UDP subscription
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.subscribe)
        # Timer to update display 
        self.displayTimer = QtCore.QTimer(self)
        self.displayTimer.setInterval(2000)
        self.displayTimer.timeout.connect(self.display)
        # Timer to update web server
        self.webdisplayTimer = QtCore.QTimer(self)
        self.webdisplayTimer.setInterval(10000)
        self.webdisplayTimer.timeout.connect(self.webdisplay)
        # Timer to reset thermometers
        self.resetMMR3Timer = QtCore.QTimer(self)
        self.resetMMR3Timer.setInterval(150000)
        self.resetMMR3Timer.timeout.connect(self.resetMMR3)        
        # UDP socket
        self.udp=QtNetwork.QUdpSocket(self)
        self.udp.bind(12000)
        self.udp.readyRead.connect(self.process)
        # Last values
        self.lastvalues = []
        for m in modules:
            self.lastvalues.extend([ (c, {'value':None,'time':None,'status':None} ) for c in m['channels'] if c])
        self.lastvalues = OrderedDict(self.lastvalues)
        l = [len(k) for k in self.lastvalues.iterkeys()]
        self.fmtstring = '{{0:{0}s}} {{1}} {{2}} {{3}}'.format(max(l))
        self.newvalues = dict()
        # Start
        self.start()
        self.displayTimer.start()
        self.webdisplayTimer.start()
        #ZMQ server
        self.zmqserver = ZMQserver(self.__call__)
        self.zmqserver.start()

    def subscribe(self):
        self.send('MES 1')

    def start(self):
        self.subscribe()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.send('MES 0')

    def send(self, msg):
        for m in modules:
            self.udp.writeDatagram(msg, QtNetwork.QHostAddress(m['ip']), m['port'])

    def process(self):
        fmt = '<BBHBBIHHdddddd'
        lenframe = struct.calcsize(fmt)
        t = time.time()
        while self.udp.hasPendingDatagrams():
            datagram, host, port = self.udp.readDatagram( self.udp.pendingDatagramSize() )
            for m in modules:
                if host.toString()== m['ip']:
                    m['isalive']=True
                    for i in range(len(datagram)/lenframe):
                        # Frame decoding
                        param = struct.unpack_from(fmt, datagram, i*lenframe)
                        if param[0]==0:
                            channel = param[1]
                            status = param[7]
                            value = param[13]
                            # Update values                            
                            if m['channels'][channel] :
                                channel_name = m['channels'][channel]
                                channel = self.lastvalues[channel_name]
                                channel['value'] = value
                                channel['time'] = t
                                channel['status'] = status
                                self.newvalues[ channel_name ] = dict(value=value,time=int(t),status=status,flag=True)

    def display(self):
        self.ui.textEdit.clear()
        for c,lv in self.lastvalues.iteritems():
            if lv['value']:
                val = '{0:7.3f} K'.format(lv['value']) if lv['value'] > 1 else '{0:6.2f} mK'.format(lv['value']*1e3)
                status = '0x{0:04x}'.format(lv['status'])
                tim = time.time() - lv['time']
                tim = '{0:4.2f} s ago'.format(tim) if tim<10 else ' >10 s ago'
            else:
                val = ''
                status = ''
                tim = ''
            self.ui.textEdit.append( self.fmtstring.format(c, val, status, tim) )
            
    def webdisplay(self):
        # Gather data of interest
        data = [ (v['time'], c,  v['value']) for c,v in self.newvalues.iteritems() if (c=='MC RuO2' or c=='MC Cernox' or c=='Still') and v['flag'] and (v['status']==0x8000 or v['status']==0x8080)]    
        # Set new flag to False
        for v in self.newvalues.itervalues() : v['flag']=False
        # Sort data by timestamp
        data.sort(key=lambda x : x[0])
        # Gather data with the same timestamp
        timestamp = None
        postdata = []
        while data:
            d = data.pop()
            if d[0]!=timestamp:
                timestamp = d[0]
                postdata.append({'timestamp':timestamp, d[1]:d[2]})
            else:
                postdata[-1][d[1]] = d[2]
        # Send data
        for body in postdata:    
            try:
                r = requests.post('https://safe-coast-63973.herokuapp.com/log', data = body, timeout=5)                
            except:
                print 'Error while posting data to the web'
        
    def resetMMR3(self):
        for m in modules:
            if not m['isalive']:
                print 'Turning power off on port',m['POE_port']
                resetport(m['POE_port'])
                m['isalive']=True
            else:
                m['isalive']=False

    def __call__(self, key):
        return self.lastvalues[key]['value']


if __name__=="__main__":
    app=QtGui.QApplication(sys.argv)
    main=MainWindow()
    main.show()
    app.exec_()
    main.zmqserver.terminate()
