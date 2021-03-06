import argparse, logging, math, os, socket, struct, sys, textwrap, time
	 
# USAGE: sudo python pmonCap.py [-h] [-v] -f FILE -d DESTINATION -t TRAINS -c CARS --locomotive-size --bigger-car-size --smaller-car-size --caboose-size --max-hops --timeout
#
# Coded using Python 2.7
#
# Author: Wladimir Cabral
# 	  wladimircabral@gmail.com
#
# This software is distributed under the MIT License: http://www.opensource.org/licenses/mit-license.php

# GLOBAL VARIABLES
MAX_HOPS = 30
TIMEOUT = 2
LOCOMOTIVE_SIZE = 1500
GROUP1_CAR_SIZE = 500
GROUP2_CAR_SIZE = 50
CABOOSE_SIZE = 28

# GLOBAL CONSTANTS
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_PROTOCOL_NUMBER = 1

# Returns the number of hops till destination. It's a variation of traceroute.
def hop_counter(dest_addr):
	ttl = 1 # ttl initial value
	destinationReached = hopCountExceeded = False
	while not (destinationReached or hopCountExceeded):
		# Create a socket for receiving data
		recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
		recv_socket.settimeout(TIMEOUT) # set timeout
		# Create a socket for sending data
		send_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
		send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl) # set ttl
		icmp_packet = create_icmp_packet(0, 'request') # create an ICMP packet
		send_socket.sendto(icmp_packet, (dest_addr, 1)) # send packet to destination
		curr_addr = None
		try: # Get the address from receiving messages
			_, curr_addr = recv_socket.recvfrom(512)
			curr_addr = curr_addr[0]
		except socket.error:
			pass
		finally: # Close sockets
			send_socket.close()
			recv_socket.close()
		if curr_addr == dest_addr: # check whether the address from current receiving message is actually the destination address
			destinationReached = True # destination reached
		else:
			ttl += 1
			if ttl > MAX_HOPS: # check whether hop count exceeded
				hopCountExceeded = True
	if destinationReached: # destination was successfully reached
		logging.getLogger('__main__').debug(str(ttl)+" hops till "+dest_addr)
		return ttl
	else: # destination could not be reached
		logging.getLogger('__main__').warn("Hop Count Exceeded!")
		sys.exit()

# Returns array of capacity estimates
def capacity_estimation(array1,array2, NUMBER_OF_CARS):
	cap_array = []
	i = 0
	while i < len(array1): # for each pair of rtts
		rtt1 = array1[i] # pick i-th element from group 1 rtt
		rtt2 = array2[i] # pick i-th element from group 2 rtt
		while rtt1 < rtt2 and i < len(array1)-1: # here we make sure rtt1 is always greater than rtt2
                    i += 1
                    rtt1 = array1[i] # pick i-th element from group 1 rtt
                    rtt2 = array2[i] # pick i-th element from group 2 rtt                        
		try:
			cap = NUMBER_OF_CARS*(GROUP1_CAR_SIZE-GROUP2_CAR_SIZE)*8/(rtt1-rtt2) # calculates capacity
			logging.getLogger('__main__').debug(str(cap)+" bps")
			cap_array.append(cap)
		except ZeroDivisionError:
			pass
		i += 1
	return cap_array		
	
# Returns end-link capacity
def capacity_calculator(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_TRAINS, NUMBER_OF_CARS):
	i = 1 # number of trains initial value
	group1_rtt_array = []
	group2_rtt_array = []
	while i <= NUMBER_OF_TRAINS: # here we will send a packet train for each group to destination
		# GROUP 1
		rtt1 = send_packet_train(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 1, i) # sends packet train
		while rtt1 == -1: # make sure there is a valid rtt value for rtt1
			logging.getLogger('__main__').warn("Unexpected RTT for GROUP1: Resending...")
			rtt1 = send_packet_train(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 1, i) # sends packet train
		# GROUP 2
		rtt2 = send_packet_train(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 2, i) # sends packet train
		while rtt2 == -1: # make sure there is a valid rtt value for rtt2
			logging.getLogger('__main__').warn("Unexpected RTT for GROUP2: Resending...")
			rtt2 = send_packet_train(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_CARS, 2, i) # sends packet train
		group1_rtt_array.append(rtt1)			
		group2_rtt_array.append(rtt2)
		group1_rtt_array.sort()
		group2_rtt_array.sort()
		logging.getLogger('__main__').debug("Capacity estimates #"+str(i)+":")
		cap_array = capacity_estimation(group1_rtt_array, group2_rtt_array, NUMBER_OF_CARS) # calculates capacity for each pair of rtts 
		i += 1
	capacity = cap_array[0] # returns the capacity value associated with the smallest pair of rtt values
	if capacity < 0:
		logging.getLogger('__main__').warn("Error on estimation of end-link capacity as MinRTT1 < MinRTT2!")
	logging.getLogger('__main__').info("End-link Capacity: "+str(capacity)+" bps")
	return capacity

# Creates a packet train
def create_packet_train(NUMBER_OF_CARS, LOCOMOTIVE_SIZE, CAR_SIZE, CABOOSE_SIZE):
	# Array of packets
	packets_array = []
	# Create LOCOMOTIVE packet
	packets_array.append(create_icmp_packet(LOCOMOTIVE_SIZE, 'reply'))
	# Create CAR packets
	i = 1 # number of cars initial value
	while i <= NUMBER_OF_CARS:
		packets_array.append(create_icmp_packet(CAR_SIZE, 'reply'))
		i += 1
	# Create CABOOSE packet
	packets_array.append(create_icmp_packet(CABOOSE_SIZE, 'request'))
	return packets_array

# Sends packet train to destination. Returns rtt.
def send_packet_train(destination_address, TTL1, TTL2, TTL3, NUMBER_OF_CARS, GROUP_NUMBER, TRAIN_NUMBER):
	# Create a packet train
	CAR_SIZE = GROUP1_CAR_SIZE if GROUP_NUMBER == 1 else GROUP2_CAR_SIZE
	packet_train = create_packet_train(NUMBER_OF_CARS, LOCOMOTIVE_SIZE, CAR_SIZE, CABOOSE_SIZE)
	# Create a socket for receiving data
	recv_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
	recv_socket.settimeout(TIMEOUT) # set timeout
	# Create a socket for sending LOCOMOTIVE packet
	send_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_PROTOCOL_NUMBER)
	send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL1) # set ttl
	send_socket.sendto(packet_train[0], (destination_address, 1)) # send LOCOMOTIVE packet to destination
	t0 = time.time() # register sending time
	# Set socket for sending CARS packets
	i = 1 # number of cars initial value
	while i <= NUMBER_OF_CARS:
		send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL2) # set ttl
		send_socket.sendto(packet_train[i], (destination_address, 1)) # send a CAR packet to destination
		i += 1
	# Set socket for sending CABOOSE packet
	send_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, TTL3) # set ttl
	send_socket.sendto(packet_train[i], (destination_address, 1)) # send CABOOSE packet to destination
	try:
		data = recv_socket.recv(1024) # Receive packet reply
		t1 = time.time() # register receiving time
		rtt = t1 - t0 # calculate rtt
	except:
		logging.getLogger('__main__').error("Unable to receive packet reply!", exc_info=False)
		rtt = -1
		pass
	finally: # close sockets
		send_socket.close()
		recv_socket.close()
	if rtt != -1: # only print valid rtt value
		logging.getLogger('__main__').debug("*GROUP #"+str(GROUP_NUMBER)+": Packet Train #"+str(TRAIN_NUMBER)+" --> RTT = "+str(rtt)+"s")
	return rtt

# Reads rtt from local file. Returns end-link capacity.
def rtt_file_reader(input_file, NUMBER_OF_TRAINS, NUMBER_OF_CARS):
	in_file = open(input_file) # Open file 
	i = 1 # number of groups initial value
	group1_rtt_array = []
	group2_rtt_array = []
	while i <= 2: # for each group
		logging.getLogger('__main__').debug(" ========== GROUP #"+str(i)+" - RTTs: ========== ")
		j = 1 # number of trains initial value
		while j <= NUMBER_OF_TRAINS: # for each packet train
			rtt = float(in_file.readline()) # read line (rtt) from file
			logging.getLogger('__main__').debug("*Packet Train #"+str(j)+" --> RTT = "+str(rtt)+"s") 
			if i == 1: # if group 1
				group1_rtt_array.append(rtt)
				group1_rtt_array.sort()
			else: # group 2
				group2_rtt_array.append(rtt)
				group2_rtt_array.sort()
			j += 1
		i += 1
	logging.getLogger('__main__').debug("Capacity estimates:")
	cap_array = capacity_estimation(group1_rtt_array, group2_rtt_array, NUMBER_OF_CARS) # calculates capacity for each pair of rtts
	capacity = cap_array[0] # returns the capacity value associated with the smallest pair of rtt values
	logging.getLogger('__main__').info("End-link Capacity: "+str(capacity)+" bps")
	return capacity

# Calculates checksum
def checksum(source_string):
	    sum = 0
	    countTo = (len(source_string)/2)*2
	    count = 0
	    while count<countTo:
		thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
		sum = sum + thisVal
		sum = sum & 0xffffffff
		count = count + 2

	    if countTo<len(source_string):
		sum = sum + ord(source_string[len(source_string) - 1])
		sum = sum & 0xffffffff

	    sum = (sum >> 16)  +  (sum & 0xffff)
	    sum = sum + (sum >> 16)
	    answer = ~sum
	    answer = answer & 0xffff

	    # Swap bytes
	    answer = answer >> 8 | (answer << 8 & 0xff00)

	    return answer

# Creates an ICMP packet
def create_icmp_packet(packet_size, MESSAGE_TYPE):

 	    # Check whether it's a Echo or Echo Reply Message
	    if MESSAGE_TYPE=='reply':
		icmp_echo_message = ICMP_ECHO_REPLY
	    else:
		icmp_echo_message = ICMP_ECHO_REQUEST

	    ID = os.getpid() & 0xFFFF

	    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
	    my_checksum = 0

	    # Make a dummy header with a 0 checksum.
    	    header = struct.pack("bbHHh", icmp_echo_message, 0, my_checksum, ID, 1)
	    header_size = len(header) + 20 # ICMP header length (8 bytes) + IPv4 header length (20 bytes)
	    if packet_size >= header_size: # Here we make sure packet_size = header_size + data
	    	data = (packet_size - header_size) * "Q"
	    else:
		data = ""

	    # Calculate the checksum on the data and the dummy header.
	    my_checksum = checksum(header + data)

	    # Now that we have the right checksum, we put that in. It's just easier
	    # to make up a new header than to stuff it into the dummy.
	    header = struct.pack(
		"bbHHh", icmp_echo_message, 0, socket.htons(my_checksum), ID, 1
	    )
	    packet = header + data
	    return packet	

# Sets Global Variables
def set_global_variables(maxhops, timeout, loc_size, car1_size, car2_size, cab_size):
	global MAX_HOPS, TIMEOUT, LOCOMOTIVE_SIZE, GROUP1_CAR_SIZE, GROUP2_CAR_SIZE, CABOOSE_SIZE
	MAX_HOPS = maxhops
	TIMEOUT = timeout
	LOCOMOTIVE_SIZE = loc_size
	GROUP1_CAR_SIZE = car1_size
	GROUP2_CAR_SIZE = car2_size
	CABOOSE_SIZE = cab_size

def main():

	# Gets current time
	localtime   = time.localtime()
	timeString  = time.strftime("%Y%m%d%H%M%S", localtime)

	# Creates a log dir if needed
	if not os.path.exists("./logs/"):
		os.makedirs("./logs/")

	# Creates logger and sets level to info
	logger = logging.getLogger(__name__)
	logger.setLevel(logging.INFO)

	# Creates console handler and sets level to debug
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)

	# Creates file handler and sets level to debug
	fh = logging.FileHandler("./logs/"+timeString+".out")
	fh.setLevel(logging.DEBUG)

	# Creates formatter for file and console handlers
	fh_formatter = logging.Formatter("%(asctime)s - %(message)s")
	ch_formatter = logging.Formatter("%(message)s")

	# Adds formatter to ch & fh
	ch.setFormatter(ch_formatter)
	fh.setFormatter(fh_formatter)

	# Adds ch & fh to logger
	logger.addHandler(ch)
	logger.addHandler(fh)

	# Parses the arguments
	parser = argparse.ArgumentParser(prog='sudo python main.py',
	formatter_class=argparse.RawDescriptionHelpFormatter, 
	description=textwrap.dedent(''' 
	===================== END-LINK CAPACITY CALCULATOR =====================

	Author: Wladimir Cabral
		wladimircabral@gmail.com

	*   This software is distributed under the MIT License: http://www.opensource.org/licenses/mit-license.php

	**  Coded using Python 2.7

	*** WARNING: You must have root permissions as this script uses ICMP packets.
	'''))
	parser.add_argument('-d','--destination', help='Destination IP address')
	parser.add_argument('-t','--trains', help='Number of packet trains (Default: 100)', default=100, type=int)
	parser.add_argument('-c','--cars', help='Number of car packets per train (Default: 100)', default=100, type=int)
	parser.add_argument('-f','--file', help='Input file', type=argparse.FileType('r'))
	parser.add_argument('-v','--verbose', help='Verbose', action='store_true')
	parser.add_argument('--locomotive-size', help='Locomotive Packet Size', default=1500, type=int)
	parser.add_argument('--bigger-car-size', help='Bigger Car Packet Size', default=500, type=int)
	parser.add_argument('--smaller-car-size', help='Smaller Car Packet Size', default=50, type=int)
	parser.add_argument('--caboose-size', help='Caboose Packet Size', default=28, type=int)
	parser.add_argument('--max-hops', help='Maximum Number of Hops', default=30, type=int)
	parser.add_argument('--timeout', help='Timeout', default=2, type=int)
	
	args = parser.parse_args()

	DESTINATION_NAME = args.destination
	NUMBER_OF_TRAINS = args.trains
	NUMBER_OF_CARS = args.cars
	INPUT_FILE = args.file
	VERBOSE = args.verbose

	set_global_variables(args.max_hops, args.timeout, args.locomotive_size, args.bigger_car_size, args.smaller_car_size, args.caboose_size)

	if VERBOSE: # sets logger to debug level
		logger.setLevel(logging.DEBUG)

	if INPUT_FILE: # check if input file is given
			# If so, no need to send probes as we read rtt values from it
			logger.info("File: "+str(INPUT_FILE.name))
			logger.debug("I) Reading RTT values from file...")
			rtt_file_reader(INPUT_FILE.name, NUMBER_OF_TRAINS, NUMBER_OF_CARS)
	elif not DESTINATION_NAME: # otherwise, check if destination is given
		parser.error("No destination or input file. Please add either --destination or --file")
	else: # if destination is passed instead of input file then
		
		# Try to resolve destination name
		try:
			DESTINATION_ADDRESS = socket.gethostbyname(DESTINATION_NAME)
			logger.info("Destination: "+str(DESTINATION_ADDRESS))
		except:
			logger.error("Could not resolve destination name to an ip address!", exc_info=False)
			sys.exit()						

		# I) Calculates number of hops till destination
		logger.debug("I) Running traceroute...")
		K = hop_counter(DESTINATION_ADDRESS)
		logger.debug("Done!") 

		# II) Sends probes to destination
		logger.debug("II) Sending groups of packet trains...")

		logger.debug("TRAIN = LOCOMOTIVE + CARS + CABOOSE")
	
		logger.debug("LOCOMOTIVE --> Length = "+str(LOCOMOTIVE_SIZE)+" | TTL = "+str(K-1)+" hops")
		logger.debug("GROUP1 CAR --> Length = "+str(GROUP1_CAR_SIZE)+" | TTL = "+str(K)+" hops")
		logger.debug("GROUP2 CAR --> Length = "+str(GROUP2_CAR_SIZE)+" | TTL = "+str(K)+" hops")
		logger.debug("CABOOSE --> Length = "+str(CABOOSE_SIZE)+" | TTL = "+str(K)+" hops")

		logger.debug("# of TRAINS: "+str(NUMBER_OF_TRAINS))
		logger.debug("# of CARS (PER TRAIN): "+str(NUMBER_OF_CARS))

		capacity_calculator(DESTINATION_ADDRESS, K-1, K, K, NUMBER_OF_TRAINS, NUMBER_OF_CARS)

	logger.debug("Done!")

if __name__ == '__main__':
	main()
