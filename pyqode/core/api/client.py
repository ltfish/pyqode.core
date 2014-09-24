"""
This module contains the client socket API. This API is exposed to the
user throught the backend manager (
:class:`pyqode.core.managers.BackendManager`)

"""
import json
import logging
import socket
import struct
import uuid
from pyqode.qt import QtCore, QtNetwork


def _logger():
    return logging.getLogger(__name__)


#: Dictionary of socket errors messages
SOCKET_ERROR_STRINGS = {
    0: 'the connection was refused by the peer (or timed out).',
    1: 'the remote host closed the connection.',
    2: 'the host address was not found.',
    3: 'the socket operation failed because the application lacked the '
       'required privileges.',
    4: 'the local system ran out of resources (e.g., too many sockets).',
    5: 'the socket operation timed out.',
    6: "the datagram was larger than the operating system's limit (which can "
       "be as low as 8192 bytes).",
    7: 'an error occurred with the network (e.g., the network cable was '
       'accidentally plugged out).',
    # 9 and 10 are UDP only, we only care about TCP.
    # all others erros are unlikely to happen in our case (proxy related
    # errors)
    - 1: 'an unidentified error occurred.',
}

#: Dictionary of process errors messages
PROCESS_ERROR_STRING = {
    0: 'the process failed to start. Either the invoked program is missing, '
       'or you may have insufficient permissions to invoke the program.',
    1: 'the process crashed some time after starting successfully.',
    2: 'the last waitFor...() function timed out. The state of QProcess is '
       'unchanged, and you can try calling waitFor...() again.',
    4: 'an error occurred when attempting to write to the process. '
       'For example, the process may not be running, or it may have closed '
       'its input channel.',
    3: 'an error occurred when attempting to read from the process. '
       'For example, the process may not be running.',
    5: 'an unknown error occurred. This is the default return value of '
       'error().'
}


class JsonTcpClient(QtNetwork.QTcpSocket):
    """
    A json tcp client socket used to start and communicate with the pyqode
    backend.

    It uses a simple message protocol. A message is made up of two parts.
    parts:
      - header: contains the length of the payload. (4bytes)
      - payload: data as a json string.

    """
    #: Internal signal emitted when the backend request finished and the
    #: socket can be removed from the list of sockets maintained by the
    #: backend manager
    finished = QtCore.Signal(QtNetwork.QTcpSocket)

    def __init__(self, parent, port, worker_class_or_function, args,
                 on_receive=None):
        super(JsonTcpClient, self).__init__(parent)
        self._port = port
        self._worker = worker_class_or_function
        self._args = args
        self._header_complete = False
        self._header_buf = bytes()
        self._to_read = 0
        self._data_buf = bytes()
        self._callback = on_receive
        self.is_connected = False
        self.connected.connect(self._on_connected)
        self.error.connect(self._on_error)
        self.disconnected.connect(self._on_disconnected)
        self.readyRead.connect(self._on_ready_read)
        self._connect()

    def _send_request(self):
        """
        Requests a work on the backend.

        :param worker_class_or_function: Class or function to execute remotely.
        :param args: worker args, any Json serializable objects
        :param on_receive: an optional callback executed when we receive the
            worker's results. The callback will be called with two arguments:
            the status (bool) and the results (object)

        :raise: BackendController.NotConnected if the backend cannot
            be reached.
        """
        classname = '%s.%s' % (self._worker.__module__, self._worker.__name__)
        self.request_id = str(uuid.uuid4())
        self.send({'request_id': self.request_id, 'worker': classname,
                   'data': self._args})

    def send(self, obj, encoding='utf-8'):
        """
        Sends a python object to the backend. The object must be JSON
        serialisable.

        :param obj: object to send
        :param encoding: encoding used to encode the json message into a
            bytes array, this should match CodeEdit.file.encoding.
        """
        _logger().debug('sending request: %r', obj)
        msg = json.dumps(obj)
        msg = msg.encode(encoding)
        header = struct.pack('=I', len(msg))
        self.write(header)
        self.write(msg)

    @staticmethod
    def pick_free_port():
        """ Picks a free port """
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.bind(('127.0.0.1', 0))
        free_port = int(test_socket.getsockname()[1])
        test_socket.close()
        return free_port

    def _connect(self):
        """ Connects our client socket to the backend socket """
        _logger().debug('connecting to 127.0.0.1:%d', self._port)
        address = QtNetwork.QHostAddress('127.0.0.1')
        self.connectToHost(address, self._port)

    def _on_connected(self):
        """ Logs connected """
        _logger().debug('connected to backend: %s:%d',
                        self.peerName(), self.peerPort())
        self.is_connected = True
        self._send_request()

    def _on_error(self, error):
        """
        Logs socket error, retry connecting if error is
        ConnectionRefusedError
        """
        if error not in SOCKET_ERROR_STRINGS:  # pragma: no cover
            error = -1
        _logger().debug(SOCKET_ERROR_STRINGS[error])
        if error == 0:
            QtCore.QTimer.singleShot(100, self._connect)

    def _on_disconnected(self):
        """ Logs disconnected """
        try:
            _logger().debug('disconnected from backend: %s:%d',
                            self.peerName(), self.peerPort())
        except (AttributeError, RuntimeError):
            # logger might be None if for some reason qt deletes the socket
            # after python global exit
            pass
        try:
            self.is_connected = False
        except AttributeError:
            pass

    def _read_header(self):
        """ Reads message header """
        _logger().debug('reading header')
        self._header_buf += self.read(4)
        if len(self._header_buf) == 4:
            self._header_complete = True
            try:
                header = struct.unpack('=I', self._header_buf)
            except TypeError:
                # pyside
                header = struct.unpack('=I', self._header_buf.data())
            self._to_read = header[0]
            self._header_buf = bytes()
            _logger().debug('header content: %d', self._to_read)

    def _read_payload(self):
        """ Reads the payload (=data) """
        _logger().debug('reading payload data')
        _logger().debug('remaining bytes to read: %d', self._to_read)
        data_read = self.read(self._to_read)
        nb_bytes_read = len(data_read)
        _logger().debug('%d bytes read', nb_bytes_read)
        self._data_buf += data_read
        self._to_read -= nb_bytes_read
        if self._to_read <= 0:
            try:
                data = self._data_buf.decode('utf-8')
            except AttributeError:
                data = bytes(self._data_buf.data()).decode('utf-8')
            _logger().debug('payload read: %r', data)
            _logger().debug('payload length: %r', len(self._data_buf))
            _logger().debug('decoding payload as json object')
            obj = json.loads(data)
            _logger().debug('response received: %r', obj)
            results = obj['results']
            status = obj['status']
            # possible callback
            if self._callback:
                self._callback(status, results)
            self._header_complete = False
            self._data_buf = bytes()
            self.finished.emit(self)

    def _on_ready_read(self):
        """ Read bytes when ready read """
        while self.bytesAvailable():
            if not self._header_complete:
                self._read_header()
            else:
                self._read_payload()


class ServerProcess(QtCore.QProcess):
    """
    Extends QProcess with methods to easily manipulate the backend process.

    Also logs everything that is written to the process' stdout/stderr.
    """
    def __init__(self, parent):
        super(ServerProcess, self).__init__(parent)
        self.started.connect(self._on_process_started)
        self.error.connect(self._on_process_error)
        self.finished.connect(self._on_process_finished)
        self.readyReadStandardOutput.connect(self._on_process_stdout_ready)
        self.readyReadStandardError.connect(self._on_process_stderr_ready)
        self.running = False
        self.starting = True
        self._srv_logger = logging.getLogger('pyqode.backend')
        self._test_not_deleted = False

    def _on_process_started(self):
        """ Logs process started """
        _logger().info('backend process started')
        self.starting = False
        self.running = True

    def _on_process_error(self, error):
        """ Logs process error """
        if error not in PROCESS_ERROR_STRING:
            error = -1
        try:
            self._test_not_deleted
        except AttributeError:
            pass
        else:
            if self.running:
                _logger().debug(PROCESS_ERROR_STRING[error])

    def _on_process_finished(self, exit_code):
        """ Logs process exit status """
        _logger().info('backend process finished with exit code %d', exit_code)
        try:
            self.running = False
        except AttributeError:
            pass

    def _on_process_stdout_ready(self):
        """ Logs process output """
        try:
            o = self.readAllStandardOutput()
            try:
                output = bytes(o).decode('utf-8')
            except TypeError:
                output = bytes(o.data()).decode('utf-8')
            output = output[:output.rfind('\n')]
            for line in output.splitlines():
                self._srv_logger.debug(line)
        except RuntimeError:
            pass

    def _on_process_stderr_ready(self):
        """ Logs process output (stderr) """
        if not self:
            return
        o = self.readAllStandardError()
        try:
            output = bytes(o).decode('utf-8')
        except TypeError:
            output = bytes(o.data()).decode('utf-8')
        output = output[:output.rfind('\n')]
        for line in output.splitlines():
            self._srv_logger.error(line)

    def terminate(self):
        """ Terminate the process """
        self.running = False
        try:
            super(ServerProcess, self).terminate()
        except RuntimeError:
            pass
