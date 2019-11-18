import hashlib
import os
import pickle
import socket
import shutil
from threading import Thread

import constants  # if highlighted - still don't care, it works

ds1_ip = constants.ds1_ip
ds2_ip = constants.ds2_ip
ds3_ip = constants.ds3_ip
ns_ip = constants.ns_ip
client_ip = constants.client_ip
ftp_port = constants.ftp_port
ns_client_port = constants.ns_client_port
ns_ds_port = constants.ns_ds_port
ds_ds_tcp_port = constants.ds_ds_tcp_port
ds_ns_port = constants.ds_ns_port

file_structure = dict()  # format - path : list of directories and files inside
current_folder = "/"  # string with the path of current folder
servers = []  # list of Data Servers, format of server: [ip: str, free space: float]
path_map = dict()  # format - path/filename : [hashcode, file info, availability]


def client_server():
    host = ns_ip
    port = ns_client_port

    server_socket = socket.socket()
    server_socket.bind(('', port))
    while True:
        server_socket.listen(2)
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
                elif data == "Delete directory":
                    rmdir(conn)
                elif data == "Read directory":
                    readdir(conn)
                elif data == "Open directory":
                    opendir(conn)
                elif data == "Create file":
                    mkfile(conn)
                elif data == "Delete file":
                    rmfile(conn)
                elif data == "File info":
                    file_info(conn)
                elif data == "Copy file":
                    copy_file(conn)
                elif data == "Move file":
                    move_file(conn)
                elif data == "Initialize":
                    msg = start_storage(data, ds1_ip, ns_ds_port)
                    conn.send(pickle.dumps(msg))
                elif data == "Help":
                    conn.send(pickle.dumps(messages))
                elif data == "Clear":
                    file_structure.clear()
                    file_structure["/"] = []
                    path_map.clear()
                    msg = "Clear"
                    response = storage_server(msg, "")
                    if response == "Clear":
                        msg = "Cleared"
                        conn.send(pickle.dumps(msg))
                elif data == "Connect":
                    msg = "IP:"
                    conn.send(pickle.dumps(msg))
                    pickle.loads(conn.recv(1024))
                    msg = "{}:{}".format(ds1_ip, ftp_port)
                    conn.send(pickle.dumps(msg))

                    directory = pickle.loads(conn.recv(1024))
                    print(directory)

                    print(os.path.isdir(directory))
                    if os.path.isdir(directory) is True:
                        msg = "Enter the filename: "
                        conn.send(pickle.dumps(msg))
                        filename = pickle.loads(conn.recv(1024))
                        print(filename)
                        path = directory + filename
                        hashed_path = calc_hash(path)
                        conn.send(pickle.dumps(hashed_path))
                        print("Waiting for connection from DS")
                        ds_ns = Thread(target=DS_NS_connection, args=())
                        ds_ns.start()
                        ds_ns.join()
                    else:
                        conn.send(pickle.dumps("No such directory"))
                        print(directory)
            else:
                data = "No such command"
                conn.send(pickle.dumps(data))

        conn.close()


def DS_NS_connection():
    print("DSNS in server")
    ds_ns = socket.socket()
    ds_ns.bind(('', ds_ns_port))
    ds_ns.listen(2)
    ds_ns, address = ds_ns.accept()
    print("Connection from: " + str(address))
    info = pickle.loads(ds_ns.recv(1024))
    print(info)
    ds_ns.close()


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
            path += "/{}".format(path_list[i])
        path += "/"
        print("Line153", name)
        print(path)
        remove_dir(conn, "{}{}/".format(current_folder, name))

        path_content = file_structure.get("{}{}".format(current_folder, path))
        print(path_content)
        path_content.remove(deleted_path)
        file_structure["{}{}/".format(current_folder, name)] = path_content
        msg = "Directory deleted"
        print(file_structure)
        conn.send(pickle.dumps(msg))
    else:
        msg = "No such directory"
        print(file_structure)
        conn.send(pickle.dumps(msg))


def remove_dir(conn, dir):
    path_content = file_structure.get(dir)
    print("Line 169")
    for elem in path_content:
        if file_structure.get("{}{}/".format(dir, elem)) is not None:
            remove_dir(conn, "{}{}/".format(dir, elem))
        else:
            remove_file(conn, elem, dir)
    file_structure.pop(dir)


def remove_file(conn, name, path):
    path_content = file_structure.get(path)
    if name not in path_content:
        print(name)
        msg = "No such file"
        return msg
    elif file_structure.get("{}{}/".format(path, name)) is not None:
        msg = name + " is directory"
        return msg
    else:
        msg = "Delete file"
        status, response = storage_server(msg, calc_hash("{}{}".format(path, name)))
        if status == "Success":
            print("Line190")
            path_content.remove(name)
            file_structure[path] = path_content
            path_map.pop("{}{}".format(path, name))
            return "Success"
        else:
            msg = "Error: {}".format(response)
            return msg
    return


def readdir(conn):
    dir = current_folder
    if file_structure.get(dir) is not None:
        print(file_structure)
        path_content = file_structure.get(dir)
        if len(path_content) == 0:
            conn.send(pickle.dumps("Empty directory"))
        else:
            data = pickle.dumps(path_content)
            conn.send(data)
    else:
        err = "No such file or directory: " + dir
        print(file_structure)
        conn.send(pickle.dumps(err))


def opendir(conn):
    conn.send(pickle.dumps("\nEnter the name of directory"))
    print(file_structure)
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
        status, response = storage_server(msg, calc_hash("{}{}".format(current_folder, filename)))
        if status == "Success":
            path_content.append(filename)
            file_structure[current_folder] = path_content
            consid_file(response, current_folder, filename)
            conn.send(pickle.dumps(response))
        else:
            msg = "Error: {}".format(response)
            conn.send(pickle.dumps(msg))


def rmfile(conn):  # TODO in DS recreate file
    conn.send(pickle.dumps("\nEnter the name of file"))
    name = pickle.loads(conn.recv(1024))
    msg = remove_file(conn, name, current_folder)
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
    status, response = storage_server("Copy file", "{} {}".format(calc_hash("{}{}".format(source, filename)),
                                                                  calc_hash("{}{}".format(destination, filename))))
    consid_file(response, destination, filename)
    dest_content = file_structure[destination]
    dest_content.append(filename)
    file_structure[destination] = dest_content
    msg = "File copied successfully."
    conn.send(pickle.dumps(msg))


def consid_file(response, path, filename):  # TODO write file info after Uploading and replication
    file_info = response
    hashcode = calc_hash("{}{}".format(path, filename))
    path_map["{}{}".format(path, filename)] = [hashcode, file_info, [True] * 3]


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
    status, response = storage_server("Move file", "{} {}".format(calc_hash("{}{}".format(source, filename)),
                                                                  calc_hash("{}{}".format(destination, filename))))
    consid_file(response, destination, filename)
    dest_content = file_structure[destination]
    dest_content.append(filename)
    file_structure[destination] = dest_content
    source_content = file_structure[source]
    source_content.remove(filename)
    file_structure[source] = source_content
    file = path_map.pop("{}{}".format(source, filename))
    path_map["{}{}".format(destination, filename)] = file
    msg = "File moved successfully."
    conn.send(pickle.dumps(msg))


def calc_hash(file_path):
    return hashlib.sha256(file_path.encode()).hexdigest()


def start_storage(msg, ip, port):
    client_socket = socket.socket()
    client_socket.connect((ip, port))
    client_socket.send(pickle.dumps(msg))
    data = pickle.loads(client_socket.recv(1024))
    if data == "Server started":
        return data
    else:
        return "Error"


def storage_server(message, path):
    host = ds1_ip
    port = ns_ds_port
    client_socket = socket.socket()
    client_socket.connect((host, port))

    client_socket.send(pickle.dumps(message))

    data = pickle.loads(client_socket.recv(1024))
    if data == "Ready":
        client_socket.send(pickle.dumps(path))
        response = pickle.loads(client_socket.recv(1024))
        client_socket.close()
        return "Success", response
    elif data == "Clear":
        return data
    else:
        print("Error")
        client_socket.close()
        return "Error", data


def ping(connection):
    hostname = connection
    response = os.system("ping -c 1 " + hostname)

    # and then check the response...
    if response == 0:
        print(hostname, 'is up!')
    else:
        print(hostname, 'is down!')


if __name__ == '__main__':
    messages = ["Initialize",
                "Create file", "Delete file", "File info", "Copy file", "Move file",
                "Open directory", "Read directory", "Make directory", "Delete directory",
                "Connect", "Clear", "Help"]
    file_structure.update({'/': []})
    print(file_structure)
    client_server()

