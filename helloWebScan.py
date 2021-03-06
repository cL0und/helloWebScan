import asyncio, aiohttp
import json, time, sys
import itertools
import queue
from threading import Thread
from bs4 import BeautifulSoup
from optparse import OptionParser


START_TIME = time.time()

HEADERS = {
	"Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	"Upgrade-Insecure-Requests":"1",
	"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:64.0) Gecko/20100101 Firefox/64.0",
	"Connection":"close",
	"Accept-Language":"en-US",
	"Accept-Encoding":"gzip, deflate"
}
SEPARATOR = ' ~~ '

def banner():
	print("""
 _          _ _    __        __   _                         
| |__   ___| | | __\\ \\      / /__| |__  ___  ___ __ _ _ __  
| '_ \\ / _ \\ | |/ _ \\ \\ /\\ / / _ \\ '_ \\/ __|/ __/ _` | '_ \\ 
| | | |  __/ | | (_) \\ V  V /  __/ |_) \\__ \\ (_| (_| | | | |
|_| |_|\\___|_|_|\\___/ \\_/\\_/ \\___|_.__/|___/\\___\\__,_|_| |_|v1.1 power by cl0und
""")

def decorator(func):
	def wrapper(*args, **kwargs):
		cr = func(*args, **kwargs)
		cr.send(None)
		return cr
	return wrapper

def genProgressBar():
	global task_number
	global completion_number
	#print(task_number,completion_number)
	completion_number += 1
	percentage = (completion_number*1.0 / task_number)*100
	print('#'*int(percentage) + ' | ' +str(float('%.2f' % percentage)) + '%', end='\r')
	sys.stdout.flush()
	if task_number == completion_number:
		print("\n[+]Please wait patiently for a few seconds.")

def readMasscanJsonFile(path):
	with open(path, 'r', encoding='utf-8') as f:
		for line in f:
			if line.startswith('{'):
				target = json.loads(line)
				yield(target['ip'], target['ports'][0]['port'])


def writefile(result):
	with open(log_filename, 'a+', encoding='utf-8') as f:
		result = json.dumps(result, ensure_ascii=False)
		try:
			f.write(result+'\n')
		except UnicodeEncodeError as e:
			print(e)

@decorator
def calcIpRange(cidrs,ports="80"):
	cidrs = [i for i in cidrs.split(',') if i != '']
	ports = [i for i in ports.split(',') if i != '']

	try:
		for cidr,port in itertools.product(cidrs,ports):
			ipstr, mask = cidr.split('/')
			mask = int(mask)
			ip_num =  "".join(["{0:08b}".format(int(num)) for num in ipstr.split('.')])
			network_number = int(ip_num[0:mask],2)
			host_number = int(ip_num[mask:],2)
			offset = 32-mask
			max_number = 2**offset

			for i in range(host_number, max_number):
				ip =  (network_number<<offset)+i
				ip ='.'.join([str(ip >> (i << 3) & 0xFF) for i in range(0, 4)[::-1]])
				yield (ip, port)
	except Exception as e:
		print(e)
		sys.exit(1)


def getTitle(result):
	try:
		soup = BeautifulSoup(result['http_body'], 'lxml')
		title = soup.title.text.strip() if hasattr(soup.title, 'text') else 'TITLE_NOT_EXSIST'
		del result['http_body']
		result['http_title'] = title
		return result
	except Exception as e:
		print(e)
		sys.exit(1)

def filterHeaders(result, headers=('Server', 'X-Powered-By')):
	try:
		http_headers = result['http_headers']
		middleware = ''
		for j in headers:
			middleware += http_headers[j] if (j in http_headers) else SEPARATOR
		del result['http_headers']
		result['middleware'] = middleware
		return result
	except Exception as e:
		print(e)
		sys.exit(1)

def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
    
async def scan(ip, port):
		async with aiohttp.ClientSession() as session:
			try:
				#genProgressBar()
				url = "http://" + ip + ":" + str(port)
				#print(url)
				async with session.get(url, verify_ssl=False, timeout=5) as resp:
					content = await resp.read()
					q.put({'url':url, 'http_code':resp.status, 'http_headers':resp.headers, 'http_body':content})
					#return {'url':url, 'http_code':resp.status, 'http_headers':resp.headers, 'http_body':content}
			except Exception as e:
				q.put(0)
				#print(e)


if __name__ == '__main__':
	banner()

	usage = """usage:
	python3 %prog -f massanJsonOutput.txt
	python3 %prog -r 192.168.99.0/24,192.168.98.0/24 -p 80,8080,8081"""
	version="%prog 1.1"

	parser =OptionParser(usage=usage, version=version)
	parser.add_option("-f", "--filename", action="store", type="string", dest="filename", help="Enter the JSON format file path generated by masscan")
	parser.add_option("-r", "--range", action="store", type="string", dest="range", help="IP address range such as 192.168.99.0/24")
	parser.add_option("-p",	"--port", action="store", type="string", dest="port", default="80", help="Set port, default is 80")
	parser.add_option("-q", "--queue", action="store", type="int", default=500, dest="queue", help="Set the value of concurrent queue, default is 500")
	parser.add_option("-o", "--outputfile", action="store", type="string", default="log.txt", dest="outputfile", help="The path of output file, the default is a timestamp-related filename")
	
	options, args = parser.parse_args()

	if options.filename != None:
		targets = readMasscanJsonFile(options.filename)
		completion_number = 0
		task_number = len(list(readMasscanJsonFile(options.filename)))
	elif options.range !=None and options.port != None:
		targets = calcIpRange(options.range, options.port)
		completion_number = 0
		task_number = len(list(calcIpRange(options.range, options.port)))
	else:
		parser.error("Missing parameters, use - h to view help")

	q = queue.Queue()

	log_filename = '_'.join(map(str,time.localtime(time.time())[0:5])) + '.txt'

	new_loop = asyncio.new_event_loop()
	t = Thread(target=start_loop, args=(new_loop,))
	t.setDaemon(True)
	t.start()

	for i in range(options.queue):
		try:
			ip, port = targets.__next__()
		except Exception as e:
			break
		asyncio.run_coroutine_threadsafe(scan(ip, port), new_loop)

	func_data = lambda x : writefile(filterHeaders(getTitle(x)))
	try:
		FLAG = 1
		while FLAG:
			if not q.empty():
				#print(completion_number)
				genProgressBar()
				result = q.get()
				if result != 0:
					func_data(result)
				try:
					ip, port = targets.__next__()
					asyncio.run_coroutine_threadsafe(scan(ip, port), new_loop)
				except StopIteration as e:
					print(e)
					FLAG = 0
			else:
				#print("sleep")
				time.sleep(0.5)
			#genProgressBar()

		time.sleep(5)
		
		while not q.empty():
			genProgressBar()
			result = q.get()
			if result != 0:
				func_data(result)

	except KeyboardInterrupt as e:
		print(e)
		new_loop.stop()

	END_TIME = time.time()

	print("\nScan over and log in %s.\nIt took %0.2f seconds altogether, with an average of %0.2f second per target." % (log_filename, END_TIME-START_TIME, END_TIME-START_TIME/task_number))