# TLS_Playback


## Dependencies

```sh
$ pip3 install termcolor
```

## Usage

```
    _____ _    ___   ___ _           _             _
   |_   _| |  / __| | _ \ |__ _ _  _| |__  __ _ __| |__
     | | | |__\__ \ |  _/ / _` | || | '_ \/ _` / _| / /
     |_| |____|___/ |_| |_\__,_|\_, |_.__/\__,_\__|_\_\
                                |__/

Usage: ./tls_playback.py -h <host> [options]


      -b, --block_len=BYTES   Bytes to use in socket.recv() methods.
                              Default: 8192
                -d, --debug   Enables debug information. Default: disabled
         --default_decision   Default action to do when an EarlyData packet is
                              detected. Options:
                               - Skip: Ignores the packet.
                               - Manual: Asks the user what to do.
                              Default: Manual
                 -h, --host   Server IP. MANDATORY
                 -k, --kill   Kill connections to force Early Data requests.
                              Default: Disabled
       --kill_delay=SECONDS   If -k is enabled, wait n seconds after the last
                              ApplicationData packet came from Server.
                              Default: 2
 --length_deviation=PERCENT   Max length deviation to match a tag. Default: 0
      --listen_addr=ADDRESS   Sets the address to listen in. Default: 0.0.0.0
         --listen_port=PORT   Sets the port to listen in. Default: 4443
            -m, --mode=MODE   Possible modes are:
                               - monitor Early Data packages are shown but it
                                         is not possible to perform replays.
                               - no_protections Best mode to use against servers
                                                without anti-replay features.
                               - protections Best mode to use against servers
                                             with anti-replay features.
                                             It forces the browser to retry the
                                             request.
                              Default: monitor
            -p, --port=PORT   Remote port to connect. Default: 443
   -r, --read_template=FILE   Reads a file containing tag information.
     --replay_delay=SECONDS   Seconds to wait after early data is replayed,
                              before close the socket. Default: 1
       --template_decisions   Uses the decisions saved in the template file.
                              Default: Disabled
  -w, --write_template=FILE   Writes the tag information in a file.

```
