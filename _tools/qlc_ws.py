#!/usr/bin/env python3
"""Client minimale (solo libreria standard) per la Web API di QLC+ (v4 e v5 >= 5.2, avviati con -w).

Uso da riga di comando:
  python3 _tools/qlc_ws.py "QLC+API|getFunctionsList"
  python3 _tools/qlc_ws.py "QLC+API|getChannelsValues|1|1|14"
  python3 _tools/qlc_ws.py --noreply "QLC+API|setFunctionStatus|5|1"
Uso da Python:
  from qlc_ws import QLC;  q = QLC();  q.cmd("QLC+API|getWidgetsList")
"""
import base64, os, socket, struct, sys


class QLC:
    def __init__(self, host="127.0.0.1", port=9999, timeout=3.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET /qlcplusWS HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.s.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("handshake fallito")
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n")[0]:
            raise ConnectionError(resp.decode(errors="replace"))
        self.buf = resp.split(b"\r\n\r\n", 1)[1]

    def send(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(bytes(hdr) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("connessione chiusa")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        b0, b1 = self._read(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._read(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._read(8))[0]
        payload = self._read(n)
        return payload.decode(errors="replace")

    def cmd(self, text, expect=None):
        """Invia e attende una risposta che inizi con `expect` (default: 'QLC+API|<comando>')."""
        self.send(text)
        parts = text.split("|")
        expect = expect or "|".join(parts[:2])
        for _ in range(50):
            r = self.recv()
            if r.startswith(expect):
                return r
        return None

    def channels(self, universe=1, start=1, count=14):
        """Valori DMX (1-based) -> lista di int."""
        r = self.cmd(f"QLC+API|getChannelsValues|{universe}|{start}|{count}")
        f = r.split("|")[2:]
        # gruppi: indice|valore|tipo[|override] (4.14/5.x hanno 4 campi, versioni vecchie 3)
        step = 4 if len(f) % 4 == 0 and (len(f) < 8 or f[4] == str(start + 1)) else 3
        return [int(f[i + 1]) for i in range(0, len(f) - step + 1, step)]

    def functions(self):
        f = self.cmd("QLC+API|getFunctionsList").split("|")[2:]
        return {f[i + 1]: int(f[i]) for i in range(0, len(f) - 1, 2)}

    def widgets(self):
        f = self.cmd("QLC+API|getWidgetsList").split("|")[2:]
        return {int(f[i]): f[i + 1] for i in range(0, len(f) - 1, 2)}

    def close(self):
        self.s.close()


class QLCLive:
    """Client per uso continuo (bridge, automazioni): un thread legge tutti i messaggi in arrivo
    (risposte QLC+API e notifiche spontanee "id|valore" dei widget), le richieste sono serializzate.
    Se QLC+ non c'è o si chiude, `ok` diventa False e connect() va richiamato."""

    def __init__(self, host="127.0.0.1", port=9999):
        import queue, threading
        self.host, self.port = host, port
        self.q, self.ok, self.conn = None, False, None
        self._replies = queue.Queue()
        self._lock = threading.Lock()
        self.pushed = {}  # ultime notifiche spontanee: widget id -> valore (stringa)

    def connect(self, timeout=2.0):
        import queue, threading
        try:
            self.conn = QLC(self.host, self.port, timeout=timeout)
        except OSError:
            self.ok = False
            return False
        self.conn.s.settimeout(None)
        self._replies = queue.Queue()
        self.ok = True
        threading.Thread(target=self._reader, args=(self.conn,), daemon=True).start()
        return True

    def _reader(self, conn):
        try:
            while True:
                m = conn.recv()
                if m.startswith("QLC+API|"):
                    self._replies.put(m)
                elif "|" in m:
                    k, v = m.split("|", 1)
                    self.pushed[k] = v
        except (OSError, ConnectionError, ValueError):
            if conn is self.conn:
                self.ok = False

    def send(self, text):
        if not self.ok:
            return False
        try:
            self.conn.send(text)
            return True
        except OSError:
            self.ok = False
            return False

    def request(self, text, timeout=1.0):
        """Invia una richiesta QLC+API e restituisce i campi della risposta (dopo 'QLC+API|cmd|')."""
        import queue
        with self._lock:
            while not self._replies.empty():
                self._replies.get_nowait()
            if not self.send(text):
                return None
            want = "|".join(text.split("|")[:2])
            try:
                while True:
                    r = self._replies.get(timeout=timeout)
                    if r.startswith(want):
                        return r.split("|")[2:]
            except queue.Empty:
                return None

    def widget_status(self, wid):
        r = self.request(f"QLC+API|getWidgetStatus|{wid}")
        try:
            return int(float(r[-1])) if r else None
        except ValueError:
            return None

    def press(self, wid, release_after=0.0):
        """Pulsante: premi e rilascia (Toggle in v4: un press = cambio stato; Flash: acceso finché premuto)."""
        import time as _t
        self.send(f"{wid}|255")
        if release_after:
            _t.sleep(release_after)
        self.send(f"{wid}|0")

    def close(self):
        self.ok = False
        if self.conn:
            self.conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    noreply = "--noreply" in args
    args = [a for a in args if a != "--noreply"]
    q = QLC()
    for a in args:
        if noreply:
            q.send(a)
        else:
            print(q.cmd(a))
    q.close()
