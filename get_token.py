import sys, getopt

from PySmartCrypto.pysmartcrypto import PySmartCrypto

def main(argv):
    ip = ''
    port = ''
    try:
        opts, args = getopt.getopt(argv,"hi:p:",["ip=","port="])
    except getopt.GetoptError:
        print( 'get_token.py -ip <ip> -port <port>')
        sys.exit(2)
    if len(opts) == 0:
        print('get_token.py -ip <ip> -port <port>')
        sys.exit()
    for opt, arg in opts:
        if opt == '-h':
            print ('get_token.py -ip <ip> -port <port>')
            sys.exit()
        elif opt in ("-i", "--ip"):
            ip = arg
        elif opt in ("-p", "--port"):
            port = arg
    PySmartCrypto(ip, port)

if __name__ == "__main__":
   main(sys.argv[1:])