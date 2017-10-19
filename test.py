import socket
import time
import struct
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('',12000))
s.sendto('MES 1',( '192.168.0.51', 12051))
s.settimeout(5)
fmt = '<BBHBBIHHdddddd'
while True:
    try:
        d = s.recv(1024)
        #print 'Received',d
        for i in range(len(d)/62):
            u = struct.unpack_from(fmt, d, i*62)
            print 'Ch',u[1],'Status',u[7],' T',u[13]
    except socket.timeout:
        print 'Timeout'
