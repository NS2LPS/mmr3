import time
import telnetlib

def resetport(port_number):
    tn = telnetlib.Telnet('192.168.0.1',timeout=5)
    tn.read_until("User:")
    tn.write('admin\r\n')
    tn.read_until("Password:")
    tn.write('cryo\r\n')
    tn.read_until("TL-SG2210P>")
    tn.write('\r\n')
    tn.read_until("TL-SG2210P>")    
    tn.write('enable\r\n')
    tn.read_until("TL-SG2210P#")
    tn.write('configure\r\n')
    tn.read_until("TL-SG2210P(config)#")    
    tn.write('interface gigabitEthernet 1/0/{0}\r\n'.format(port_number))
    tn.read_until("TL-SG2210P(config-if)#")    
    tn.write('power inline supply disable\r\n')
    tn.read_until("TL-SG2210P(config-if)#")    
    time.sleep(2)
    tn.write('power inline supply enable\r\n')    
    tn.read_until("TL-SG2210P(config-if)#")    
    tn.write("exit\r\n")
    tn.close()

time.sleep(0)
resetport(6)