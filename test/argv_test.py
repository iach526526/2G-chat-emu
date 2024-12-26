import argparse
parser = argparse.ArgumentParser()
parser.add_argument("echo",help="echo the string you use here")
args = parser.parse_args()
print(args.echo)
# print(args.IP)


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Start as server or client.")
#     parser.add_argument("mode", choices=["server", "client"], help="Start as 'server' or 'client'")
#     parser.add_argument("--port", type=int, required=False, help="Port number")
#     parser.add_argument("--host", required=False, help="Server IP address (required for client mode)")