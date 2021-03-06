import hashlib
import os
import pickle
import socket
import time
from threading import Thread

import constants  # if highlighted - still don't care, it works

ns_ip = constants.ns_ip
client_ip = constants.client_ip
ftp_port = constants.ftp_port
ns_client_port = constants.ns_client_port
ns_ds_port = constants.ns_ds_port
ds_ds_tcp_port = constants.ds_ds_tcp_port
ds_ns_port = constants.ds_ns_port
new_ds_port = constants.new_ds_port

servers = []
file_structure = dict()  # format - path : list of directories and files inside
current_folder = "/"  # string with the path of current folder
path_map = dict()  # format - path/filename : [hashcode, file info]
hash_table = dict()
server_control = dict()  # format - hash : [IPs]

messages = ["Initialize", "Create file", "Delete file", "File info", "Copy file", "Move file",
            "Open directory", "Read directory", "Make directory", "Delete directory",
            "Upload", "Download", "Help", "Status"]


# HELPERS


def save_dict(obj, name):
    with open('dict/' + name + '.pkl', 'wb+') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)


def load_dict(name):
    with open('dict/' + name + '.pkl', 'rb') as f:
        return pickle.load(f)


def consid_file(path, filename):
    hashcode = calc_hash("{}{}".format(path, filename))
    if path_map.get("{}{}".format(path, filename)) is None:
        path_map["{}{}".format(path, filename)] = [hashcode, None]
    if hash_table.get(hashcode) is None:
        hash_table[hashcode] = "{}{}".format(path, filename)


def calc_hash(file_path):
    return hashlib.sha256(file_path.encode()).hexdigest()


def check_servers():
    while True:
        for ip in servers:
            hostname = ip
            response = send_message_to_ds(ip, "Check", "")

            if response != "Check":
                print(hostname, 'is down!')
                servers.remove(ip)
                for ip in servers:
                    send_message_to_ds(ip, "Update DS", servers)
                for file in server_control.keys():
                    server_list = server_control.get(file)
                    if ip in server_list:
                        server_list.remove(ip)
        time.sleep(2)


def init():
    global file_structure
    global server_control
    global path_map
    global hash_table
    if os.path.isdir("dict"):
        if os.path.isfile("dict/file_structure.pkl"):
            file_structure = load_dict("file_structure")
        if os.path.isfile("dict/server_control.pkl"):
            server_control = load_dict("server_control")
        if os.path.isfile("dict/path_map.pkl"):
            path_map = load_dict("path_map")
        if os.path.isfile("dict/hash_table.pkl"):
            hash_table = load_dict("hash_table")
    else:
        os.mkdir("dict")
        file_structure.update({'/': []})


# INSTRUCTION EXECUTORS


def mkdir(conn):
    conn.send(pickle.dumps("\nEnter the name of directory"))
    name = pickle.loads(conn.recv(1024))
    if file_structure.get(current_folder + name) is not None:
        msg = "Already exists"
        conn.send(pickle.dumps(msg))
    else:
        file_structure["{}{}/".format(current_folder, name)] = []
        path_content = file_structure.get(current_folder)
        path_content.append(name)
        file_structure[current_folder] = path_content
        msg = "Successfully created"
        print(file_structure)
        conn.send(pickle.dumps(msg))


def get_status(conn):
    print("File structure: " + str(file_structure))
    print("Servers: " + str(servers))
    print("Server control: " + str(server_control))
    print("Path map: " + str(path_map))
    print("Hash table: " + str(hash_table))
    conn.send(pickle.dumps("Success"))


def rmdir(conn):
    conn.send(pickle.dumps("\nEnter the name of directory"))
    name = pickle.loads(conn.recv(1024))
    if name == "/":
        msg = "Can't remove root directory"
        conn.send(pickle.dumps(msg))
    if file_structure.get("{}{}/".format(current_folder, name)) is not None:
        path_list = name.split("/")
        deleted_path = path_list[-1]
        path = ""
        for i in range(len(path_list) - 1):
            path += "{}/".format(path_list[i])
        remove_dir("{}{}/".format(current_folder, name))

        path_content = file_structure.get("{}{}".format(current_folder, path))
        path_content.remove(deleted_path)
        msg = "Directory deleted"
        conn.send(pickle.dumps(msg))
    else:
        msg = "No such directory"
        conn.send(pickle.dumps(msg))


def remove_dir(dir):
    path_content = file_structure.get(dir)
    for elem in reversed(path_content):
        path = "{}{}/".format(dir, elem)
        if file_structure.get(path) is not None:
            remove_dir(path)
        else:
            remove_file(elem, dir)
    file_structure.pop(dir)


def remove_file(name, path):
    path_content = file_structure.get(path)
    if name not in path_content:
        msg = "No such file"
        return msg
    elif file_structure.get("{}{}/".format(path, name)) is not None:
        msg = name + " is directory"
        return msg
    else:
        msg = "Delete file"
        success = True
        servers_with_file = server_control.get(calc_hash("{}{}".format(path, name)))
        for ip in servers_with_file:
            status = send_message_to_ds(ip, msg, calc_hash("{}{}".format(path, name)))
            if status != "Success":
                servers_with_file.remove(ip)
                success = False
        if success:
            if name in path_content:
                path_content.remove(name)
                file_structure[path] = path_content
                path_map.pop("{}{}".format(path, name))
                hash_table.pop(calc_hash("{}{}".format(path, name)))
                server_control.pop(calc_hash("{}{}".format(path, name)))
        else:
            success = False
        if success:
            return "Success"
        else:
            return "Error"


def readdir(conn):
    dir = current_folder
    if file_structure.get(dir) is not None:
        path_content = file_structure.get(dir)
        if len(path_content) == 0:
            conn.send(pickle.dumps("Empty directory"))
        else:
            data = pickle.dumps(path_content)
            conn.send(data)
    else:
        err = "No such file or directory: " + dir
        conn.send(pickle.dumps(err))


def opendir(conn):
    conn.send(pickle.dumps("\nEnter the name of directory"))
    dir = pickle.loads(conn.recv(1024))
    global current_folder
    if dir == "/":
        current_folder = "/"
        conn.send(pickle.dumps(current_folder))
    elif file_structure.get("/{}/".format(dir)) is not None:
        current_folder = "/{}/".format(dir)
        conn.send(pickle.dumps(current_folder))
    else:
        err = "No such file or directory: " + dir
        conn.send(pickle.dumps(err))


def mkfile(conn):
    conn.send(pickle.dumps("\nEnter the name of file"))
    filename = pickle.loads(conn.recv(1024))
    path_content = file_structure.get(current_folder)
    if filename in path_content:
        msg = "Already exists"
        conn.send(pickle.dumps(msg))
    else:
        msg = "Create file"
        for ip in servers:
            status = send_message_to_ds(ip, msg, calc_hash("{}{}".format(current_folder, filename)))
            if status == "Success":
                if filename not in path_content:
                    path_content.append(filename)
                    file_structure[current_folder] = path_content
                    consid_file(current_folder, filename)
            else:
                msg = "Error: {}".format(status)
        conn.send(pickle.dumps("Successfully created " + filename))


def rmfile(conn):
    conn.send(pickle.dumps("\nEnter the name of file"))
    name = pickle.loads(conn.recv(1024))
    msg = remove_file(name, current_folder)
    conn.send(pickle.dumps(msg))


def file_info(conn):
    conn.send(pickle.dumps("\nEnter the name of file"))
    filename = pickle.loads(conn.recv(1024))
    path = "{}{}".format(current_folder, filename)
    if path_map.get(path):
        info = path_map.get(path)[1]
        data = pickle.dumps(info)
        conn.send(data)
    else:
        msg = "No such file"
        conn.send(pickle.dumps(msg))


def copy_file(conn):
    conn.send(pickle.dumps("\nEnter the path of file"))
    source = pickle.loads(conn.recv(1024))
    conn.send(pickle.dumps("\nEnter the name of file"))
    filename = pickle.loads(conn.recv(1024))
    conn.send(pickle.dumps("\nEnter the destination of file"))
    destination = pickle.loads(conn.recv(1024))
    if source != "/":
        source = "/{}/".format(source)
    if destination != "/":
        destination = "/{}/".format(destination)
    if file_structure.get(source) is None:
        msg = "No such directory: {}".format(source)
        conn.send(pickle.dumps(msg))
        return
    if file_structure.get(destination) is None:
        msg = "No such directory: {}".format(destination)
        conn.send(pickle.dumps(msg))
        return
    if path_map.get("{}{}".format(source, filename)) is None:
        msg = "No such file: {}".format(filename)
        conn.send(pickle.dumps(msg))
        return
    if path_map.get("{}{}".format(destination, filename)) is not None:
        msg = "File already exist"
        conn.send(pickle.dumps(msg))
        return
    msg = "Copy file"
    for ip in servers:
        status = send_message_to_ds(ip, msg, "{} {}".format(calc_hash("{}{}".format(source, filename)),
                                                            calc_hash("{}{}".format(destination, filename))))
        if status == "Success":
            consid_file(destination, filename)
        else:
            msg = "Error: {}".format(status)
        dest_content = file_structure[destination]
        if filename not in dest_content:
            dest_content.append(filename)
            file_structure[destination] = dest_content
    msg = "File copied successfully."
    conn.send(pickle.dumps(msg))


def move_file(conn):
    conn.send(pickle.dumps("\nEnter the path of file"))
    source = pickle.loads(conn.recv(1024))
    conn.send(pickle.dumps("\nEnter the name of file"))
    filename = pickle.loads(conn.recv(1024))
    conn.send(pickle.dumps("\nEnter the destination of file"))
    destination = pickle.loads(conn.recv(1024))
    if source != "/":
        source = "/{}/".format(source)
    if destination != "/":
        destination = "/{}/".format(destination)
    if file_structure.get(source) is None:
        msg = "No such directory: {}".format(source)
        conn.send(pickle.dumps(msg))
        return
    if file_structure.get(destination) is None:
        msg = "No such directory: {}".format(destination)
        conn.send(pickle.dumps(msg))
        return
    if path_map.get("{}{}".format(source, filename)) is None:
        msg = "No such file: {}".format(filename)
        conn.send(pickle.dumps(msg))
        return
    if path_map.get("{}{}".format(destination, filename)) is not None:
        msg = "File already exists"
        conn.send(pickle.dumps(msg))
        return
    msg = "Move file"
    for ip in servers:
        status = send_message_to_ds(ip, msg, "{} {}".format(calc_hash("{}{}".format(source, filename)),
                                                            calc_hash("{}{}".format(destination, filename))))
        if status == "Success":
            consid_file(destination, filename)
        else:
            msg = "Error: {}".format(status)
        dest_content = file_structure[destination]
        if filename not in dest_content:
            dest_content.append(filename)
            file_structure[destination] = dest_content
        source_content = file_structure[source]
        if filename in source_content:
            source_content.remove(filename)
            file_structure[source] = source_content
            source_path_file = "{}{}".format(source, filename)
            path_map.pop(source_path_file)
            server_control.pop(calc_hash(source_path_file))
            hash_table.pop(calc_hash(source_path_file))
    msg = "File moved successfully."
    conn.send(pickle.dumps(msg))


def get_help(conn):
    conn.send(pickle.dumps(messages))


def clear(conn):
    file_structure.clear()
    file_structure["/"] = []
    path_map.clear()
    server_control.clear()
    hash_table.clear()
    msg = "Initialize"
    ip_id = 0
    response = send_message_to_ds(servers[ip_id], msg, "")
    if response == "Server started":
        msg = "Cleared"
        conn.send(pickle.dumps(msg))


# INTERSERVER CONNECTIONS

def listen_newcomer_ds():
    port = ds_ns_port
    server = socket.socket()
    server.bind(('', port))
    server.listen(6)

    while True:
        conn, address = server.accept()

        data = pickle.loads(conn.recv(1024))
        if data == "New":
            print("New server: " + address[0])
            servers.append(address[0])
            conn.send(pickle.dumps(servers))
            for ip in servers:
                if ip != address[0]:
                    send_message_to_ds(ip, "Update DS", servers)
            if len(servers) > 1:
                send_message_to_ds(servers[0], "Backup", address[0])
        if data == "New file":
            print("New file from " + str(address))
            conn.send(pickle.dumps("File"))
            hashcode = pickle.loads(conn.recv(1024))
            hashcode = hashcode.split("/")[-1]
            conn.send(pickle.dumps("Info"))
            file_info = pickle.loads(conn.recv(1024))
            file_containers = server_control.get(hashcode)
            if file_containers is None:
                file_containers = [address[0]]
                server_control[hashcode] = file_containers
            elif address[0] not in file_containers:
                file_containers.append(address[0])
            pt_map = path_map.values()
            for file in pt_map:
                if file[0] == str(hashcode):
                    if file[1] is None:
                        file[1] = file_info
        else:
            conn.send(pickle.dumps("Error"))
        conn.close()

        save_dict(file_structure, "file_structure")
        save_dict(path_map, "path_map")
        save_dict(server_control, "server_control")
        save_dict(hash_table, "hash_table")


def send_message_to_ds(ip, message, content):
    simple_response = ["Check", "Server started"]
    content_response = ["Ready", "Update"]
    host = ip
    port = ns_ds_port
    client_socket = socket.socket()
    try:
        client_socket.connect((host, port))
    except:
        return "Fail"

    client_socket.send(pickle.dumps(message))

    data = pickle.loads(client_socket.recv(1024))
    if data in content_response:
        client_socket.send(pickle.dumps(content))
        pickle.loads(client_socket.recv(1024))
        client_socket.close()

        save_dict(file_structure, "file_structure")
        save_dict(path_map, "path_map")
        save_dict(server_control, "server_control")
        save_dict(hash_table, "hash_table")
        return "Success"
    elif data == "Backup":
        client_socket.send(pickle.dumps(content))
        response = pickle.loads(client_socket.recv(1024))
        while response != "Finish Backup":
            client_socket.send(pickle.dumps("Received"))
            response = pickle.loads(client_socket.recv(1024))

            save_dict(file_structure, "file_structure")
            save_dict(path_map, "path_map")
            save_dict(server_control, "server_control")
            save_dict(hash_table, "hash_table")
    elif data in simple_response:

        save_dict(file_structure, "file_structure")
        save_dict(path_map, "path_map")
        save_dict(server_control, "server_control")
        save_dict(hash_table, "hash_table")
        return data
    else:
        print("Error")
        client_socket.close()
        return data


def client_server():
    port = ns_client_port

    server_socket = socket.socket()
    server_socket.bind(('', port))
    server_socket.listen(2)
    while True:
        conn, address = server_socket.accept()
        print("Connection from: " + str(address))

        while True:
            data = conn.recv(1024)
            if not data:
                break
            data = pickle.loads(data)
            if any(x == data for x in messages) is True:
                if data == "Make directory":
                    mkdir(conn)
                    save_dict(file_structure, "file_structure")
                elif data == "Delete directory":
                    rmdir(conn)
                    save_dict(file_structure, "file_structure")
                elif data == "Read directory":
                    readdir(conn)
                elif data == "Open directory":
                    opendir(conn)
                elif data == "Create file":
                    mkfile(conn)
                    save_dict(file_structure, "file_structure")
                    save_dict(path_map, "path_map")
                    save_dict(server_control, "server_control")
                    save_dict(hash_table, "hash_table")
                elif data == "Delete file":
                    rmfile(conn)
                    save_dict(file_structure, "file_structure")
                    save_dict(path_map, "path_map")
                    save_dict(server_control, "server_control")
                    save_dict(hash_table, "hash_table")
                elif data == "File info":
                    file_info(conn)
                elif data == "Status":
                    get_status(conn)
                elif data == "Copy file":
                    copy_file(conn)
                    save_dict(file_structure, "file_structure")
                    save_dict(path_map, "path_map")
                    save_dict(server_control, "server_control")
                    save_dict(hash_table, "hash_table")
                elif data == "Move file":
                    move_file(conn)
                    save_dict(file_structure, "file_structure")
                    save_dict(path_map, "path_map")
                    save_dict(server_control, "server_control")
                    save_dict(hash_table, "hash_table")
                elif data == "Initialize":
                    clear(conn)
                    save_dict(file_structure, "file_structure")
                    save_dict(path_map, "path_map")
                    save_dict(server_control, "server_control")
                    save_dict(hash_table, "hash_table")
                elif data == "Help":
                    get_help(conn)
                elif data == "Download":
                    msg = "Path"
                    conn.send(pickle.dumps(msg))
                    path = pickle.loads(conn.recv(1024))
                    if path != "Error":
                        msg = "Filename"
                        conn.send(pickle.dumps(msg))
                        filename = pickle.loads(conn.recv(1024))
                        if path != "/":
                            path = "/{}/".format(path)
                        if file_structure.get(path) is None:
                            conn.send(pickle.dumps("No target directory"))
                        elif path_map.get("{}{}".format(path, filename)) is None:
                            conn.send(pickle.dumps("File doesn't exist"))
                        else:
                            servs = server_control.get(calc_hash("{}{}".format(path, filename)))
                            if servs is None:
                                conn.send(pickle.dumps("Error"))
                            else:
                                ip = servs[0]
                                conn.send(pickle.dumps("{}:{}".format(ip, ftp_port)))
                                pickle.loads(conn.recv(1024))
                                msg = calc_hash("{}{}".format(path, filename))
                                conn.send(pickle.dumps(msg))
                elif data == "Upload":
                    msg = "Path"
                    conn.send(pickle.dumps(msg))
                    path = pickle.loads(conn.recv(1024))
                    if path != "Error":
                        msg = "Filename"
                        conn.send(pickle.dumps(msg))
                        filename = pickle.loads(conn.recv(1024))
                        if path != "/":
                            path = "/{}/".format(path)
                        if file_structure.get(path) is None:
                            conn.send(pickle.dumps("No target directory"))
                        elif path_map.get("{}{}".format(path, filename)) is not None:
                            conn.send(pickle.dumps("File already exist"))
                        else:
                            conn.send(pickle.dumps("{}:{}".format(servers[0], ftp_port)))
                            pickle.loads(conn.recv(1024))
                            msg = calc_hash("{}{}".format(path, filename))
                            conn.send(pickle.dumps(msg))
                            path_content = file_structure.get(path)
                            path_content.append(filename)
                            consid_file(path, filename)
            else:
                data = "No such command"
                conn.send(pickle.dumps(data))

        conn.close()


def get_my_ip():
    try:
        host_name = socket.gethostname()
        host_ip = socket.gethostbyname(host_name)
        return host_ip
    except:
        print("Unable to get Hostname and IP")
        return 0

if __name__ == '__main__':
    print(get_my_ip())
    init()
    new_ds_checker = Thread(target=listen_newcomer_ds, daemon=True)
    new_ds_checker.start()
    checker = Thread(target=check_servers, daemon=True)
    checker.start()
    client_server()
