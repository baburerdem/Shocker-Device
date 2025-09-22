"""
title: "Shock Device Controller for Electric Shock Avoidance Assay for Windows"
date: "22/09/2025"
author: "Babur Erdem"
update date: "22/09/2025"
"""

import sys, os, time, threading, ctypes, atexit
from PySide6 import QtCore, QtWidgets
import serial, serial.tools.list_ports
import numpy as np

# High-res timer on Windows
if os.name == "nt":
    _winmm = ctypes.WinDLL("winmm")
    _winmm.timeBeginPeriod(1)
    atexit.register(lambda: _winmm.timeEndPeriod(1))

BAUD = 115200
SPIN_WINDOW_S = 0.010

SIDE_FULL = ["None", "Upside", "Downside", "All", "Random"]
SIDE_TO_CHAR = {"None": "N", "Upside": "U", "Downside": "D", "All": "A", "Random": "R"}
CHAR_TO_SIDE = {v: k for k, v in SIDE_TO_CHAR.items()}

def now_hms(): return time.strftime("%H:%M:%S")

class Phase:
    def __init__(self, name, dur_ms, side_char):
        self.name = name; self.dur_ms = int(dur_ms); self.side = side_char

class Runner(QtCore.QThread):
    log = QtCore.Signal(str); header = QtCore.Signal(str); status = QtCore.Signal(str)
    progress = QtCore.Signal(int); currentPhase = QtCore.Signal(str); beep = QtCore.Signal(); done = QtCore.Signal()
    def __init__(self, ser, phases, rnd_steps, exp_name):
        super().__init__(); self.ser=ser; self.phases=phases[:]; self.rnd=rnd_steps[:]; self.exp=exp_name.strip(); self._stop=False
    def stop(self): self._stop=True
    def send(self,s):
        try: self.ser.write((s+"\n").encode("ascii"))
        except Exception: pass
    def _wait_until(self,t_end,total_ms=None,start_t=None):
        while not self._stop:
            now=time.perf_counter()
            if start_t is not None and total_ms is not None:
                pct=max(0,min(100,int(100*((now-start_t)*1000)/max(1,total_ms)))); self.progress.emit(pct)
            if now>=t_end: break
            rem=t_end-now
            if rem>SPIN_WINDOW_S: time.sleep(0.001)
            else:
                while not self._stop and time.perf_counter()<t_end: pass
                break
    def _hold(self,side,ms):
        self.log.emit(f"[{now_hms()}] STATE {side} for {ms} ms")
        t0=time.perf_counter(); self.send(f"MODE={side}"); self._wait_until(t0+ms/1000.0,total_ms=ms,start_t=t0)
    def _play_random_for(self,budget_ms):
        if not self.rnd: self._hold('N',budget_ms); return
        left=budget_ms; i=0; cur=None; t_end=time.perf_counter(); t0=t_end; total=budget_ms
        while not self._stop and left>0:
            ms,side=self.rnd[i]; ms=min(ms,left)
            self.log.emit(f"[{now_hms()}] R-STEP {side} for {ms} ms")
            if side!=cur: self.send(f"MODE={side}"); cur=side
            t_end+=ms/1000.0; self._wait_until(t_end,total_ms=total,start_t=t0)
            left-=ms; i=0 if i+1>=len(self.rnd) else i+1
    def run(self):
        try:
            n=len(self.phases); tag=(f"[Experiment: {self.exp}] " if self.exp else "")
            self.log.emit(f"[{now_hms()}] {tag}RUN START"); self.beep.emit()
            for k,p in enumerate(self.phases,1):
                if self._stop: break
                self.header.emit(f"{tag}PHASE {k}/{n} | {p.name} | Side={p.side} | {p.dur_ms} ms")
                self.currentPhase.emit(f"Phase {k}/{n}: {p.name} ({CHAR_TO_SIDE.get(p.side,'?')})")
                self.status.emit(f"Running — Phase {k}/{n}"); self.progress.emit(0)
                if p.side in ('N','U','D','A'): self._hold(p.side,p.dur_ms)
                else: self._play_random_for(p.dur_ms)
                self.log.emit(f"[{now_hms()}] PHASE {k} complete"); self.progress.emit(100)
                if k<n: self.beep.emit()
            self.send("MODE=N"); self.log.emit(f"[{now_hms()}] {tag}===== RUN FINISHED =====")
            self.status.emit("Done"); self.currentPhase.emit("Idle"); self.progress.emit(0); self.done.emit()
        except Exception:
            self.send("MODE=N"); self.log.emit(f"[{now_hms()}] ===== RUN ABORTED (error) =====")
            self.status.emit("Stopped"); self.currentPhase.emit("Idle"); self.progress.emit(0); self.done.emit()

class ShockGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shock Controller — Compact"); self.resize(980, 620)
        self.port=None; self.expName=""; self.phases=[]; self.rnd_raw=[]; self.rnd=[]
        self._build_ui()

    # ---------- layout ----------
    def _build_ui(self):
        root = QtWidgets.QWidget(); self.setCentralWidget(root)
        vroot = QtWidgets.QVBoxLayout(root); vroot.setContentsMargins(8,8,8,8); vroot.setSpacing(8)

        top = QtWidgets.QWidget(); vtop = QtWidgets.QVBoxLayout(top); vtop.setContentsMargins(0,0,0,0); vtop.setSpacing(4)
        row1 = QtWidgets.QHBoxLayout(); row1.setSpacing(8)
        row1.addWidget(QtWidgets.QLabel("Port:"))
        self.portBox = QtWidgets.QComboBox(); self._refresh_ports(); row1.addWidget(self.portBox, 1)
        self.btnRescan = QtWidgets.QPushButton("Rescan"); self.btnRescan.clicked.connect(self._refresh_ports); row1.addWidget(self.btnRescan)
        self.btnConnect = QtWidgets.QPushButton("Connect"); self.btnConnect.clicked.connect(self.connect_port); row1.addWidget(self.btnConnect)
        row1.addStretch(1); vtop.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout(); row2.setSpacing(8)
        self.btnStart = QtWidgets.QPushButton("Start"); self.btnStart.clicked.connect(self.start_run); row2.addWidget(self.btnStart)
        self.btnStop  = QtWidgets.QPushButton("Stop");  self.btnStop.clicked.connect(self.stop_run);  row2.addWidget(self.btnStop)
        self.btnU = QtWidgets.QPushButton("Upside");   self.btnU.clicked.connect(lambda: self._manual_mode('U')); row2.addWidget(self.btnU)
        self.btnD = QtWidgets.QPushButton("Downside"); self.btnD.clicked.connect(lambda: self._manual_mode('D')); row2.addWidget(self.btnD)
        self.btnA = QtWidgets.QPushButton("All");      self.btnA.clicked.connect(lambda: self._manual_mode('A')); row2.addWidget(self.btnA)
        self.btnN = QtWidgets.QPushButton("None");     self.btnN.clicked.connect(lambda: self._manual_mode('N')); row2.addWidget(self.btnN)
        row2.addStretch(1); vtop.addLayout(row2)
        vroot.addWidget(top)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal); vroot.addWidget(splitter, 1)

        left = QtWidgets.QWidget(); vleft = QtWidgets.QVBoxLayout(left); vleft.setContentsMargins(0,0,0,0); vleft.setSpacing(8)
        grpExp = QtWidgets.QGroupBox("Experiment"); fexp = QtWidgets.QFormLayout(grpExp)
        self.expEdit = QtWidgets.QLineEdit(); self.expEdit.setPlaceholderText("Experiment name"); fexp.addRow("Name:", self.expEdit)
        self.btnLoadRnd = QtWidgets.QPushButton("Load Random"); self.btnLoadRnd.clicked.connect(self.load_random_seq); fexp.addRow(self.btnLoadRnd)
        vleft.addWidget(grpExp)

        grpPh = QtWidgets.QGroupBox("Phase Designer"); vph = QtWidgets.QVBoxLayout(grpPh)
        grid = QtWidgets.QGridLayout()
        self.nameEd = QtWidgets.QLineEdit(); self.nameEd.setPlaceholderText("Phase name")
        self.durEd  = QtWidgets.QLineEdit(); self.durEd.setPlaceholderText("mm:ss")
        self.sideBox= QtWidgets.QComboBox(); self.sideBox.addItems(SIDE_FULL)
        addBtn = QtWidgets.QPushButton("Add"); addBtn.clicked.connect(self.add_phase)
        grid.addWidget(self.nameEd,0,0); grid.addWidget(self.durEd,0,1); grid.addWidget(self.sideBox,0,2); grid.addWidget(addBtn,0,3)
        vph.addLayout(grid)

        self.table = QtWidgets.QTableWidget(0,3)
        self.table.setHorizontalHeaderLabels(["Name","Duration","Side"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        vph.addWidget(self.table)

        horder = QtWidgets.QHBoxLayout()
        self.upB=QtWidgets.QPushButton("↑"); self.dnB=QtWidgets.QPushButton("↓"); self.delB=QtWidgets.QPushButton("Del")
        self.upB.clicked.connect(self.move_up); self.dnB.clicked.connect(self.move_down); self.delB.clicked.connect(self.del_phase)
        for b in (self.upB,self.dnB,self.delB): horder.addWidget(b)
        horder.addStretch(1); vph.addLayout(horder)
        vleft.addWidget(grpPh, 1)
        splitter.addWidget(left)

        right = QtWidgets.QWidget(); vright = QtWidgets.QVBoxLayout(right); vright.setContentsMargins(0,0,0,0); vright.setSpacing(8)
        self.status = QtWidgets.QLabel("Disconnected"); self.status.setStyleSheet("font-weight:600;"); vright.addWidget(self.status)
        hp = QtWidgets.QHBoxLayout()
        self.curPhaseLbl = QtWidgets.QLabel("Idle")
        self.progressBar = QtWidgets.QProgressBar(); self.progressBar.setRange(0,100); self.progressBar.setValue(0)
        hp.addWidget(self.curPhaseLbl); hp.addWidget(self.progressBar); vright.addLayout(hp)
        self.log = QtWidgets.QPlainTextEdit(); self.log.setReadOnly(True); vright.addWidget(self.log, 1)
        hlog = QtWidgets.QHBoxLayout()
        self.btnSaveLog = QtWidgets.QPushButton("Save Log"); self.btnSaveLog.clicked.connect(self._save_log); hlog.addWidget(self.btnSaveLog)
        self.btnClearLog = QtWidgets.QPushButton("Clear Log"); self.btnClearLog.clicked.connect(lambda: self.log.clear()); hlog.addWidget(self.btnClearLog)
        hlog.addStretch(1); vright.addLayout(hlog)

        splitter.addWidget(right); splitter.setSizes([460, 520])
        self.sb = self.statusBar(); self.sb.showMessage("Ready")

    # ---------- helpers ----------
    def _refresh_ports(self):
        self.portBox.clear()
        ports=[p.device for p in serial.tools.list_ports.comports()]
        ports_sorted=sorted(ports, key=lambda s: (not ("/dev/ttyACM" in s or "/dev/ttyUSB" in s), s))
        for dev in ports_sorted: self.portBox.addItem(dev)

    def _save_log(self):
        exp = self.expEdit.text().strip(); base = f"{exp}_" if exp else ""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save log",
                                                        f"{base}log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                                                        "Text (*.txt)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(self.log.toPlainText())
            self.sb.showMessage(f"Saved: {os.path.basename(path)}", 3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Save error", str(e))

    def mmss_to_ms(self,s):
        mm,ss=s.strip().split(":"); return (int(mm)*60+int(ss))*1000

    def _sel(self):
        r=self.table.currentRow(); return r if 0<=r<len(self.phases) else -1

    def _refresh_table(self):
        self.table.setRowCount(len(self.phases))
        for i,p in enumerate(self.phases):
            self.table.setItem(i,0,QtWidgets.QTableWidgetItem(p.name))
            self.table.setItem(i,1,QtWidgets.QTableWidgetItem(f"{p.dur_ms//1000}s"))
            self.table.setItem(i,2,QtWidgets.QTableWidgetItem(CHAR_TO_SIDE.get(p.side,"?")))
        self.table.resizeColumnsToContents()

    def _set_running_ui(self, running: bool):
        # lock editing while running
        for w in [self.nameEd,self.durEd,self.sideBox,self.upB,self.dnB,self.delB,self.table,self.expEdit,self.btnLoadRnd]:
            w.setEnabled(not running)
        # manual strictly idle-only
        self.btnU.setEnabled(not running)
        self.btnD.setEnabled(not running)
        self.btnA.setEnabled(not running)
        self.btnN.setEnabled(not running)
        # start/stop policy
        self.btnStart.setEnabled(not running)
        self.btnStop.setEnabled(running)

    # ---------- phase ops ----------
    def add_phase(self):
        try:
            name=self.nameEd.text().strip() or f"P{len(self.phases)+1}"
            dur=self.mmss_to_ms(self.durEd.text())
            side=SIDE_TO_CHAR[self.sideBox.currentText()]
        except Exception:
            QtWidgets.QMessageBox.warning(self,"Input","Duration must be mm:ss"); return
        if dur<=0:
            QtWidgets.QMessageBox.warning(self,"Input","Duration must be > 0"); return
        self.phases.append(Phase(name,dur,side)); self._refresh_table()

    def move_up(self):
        r=self._sel()
        if r>0: self.phases[r-1],self.phases[r]=self.phases[r],self.phases[r-1]; self._refresh_table(); self.table.selectRow(r-1)

    def move_down(self):
        r=self._sel()
        if 0<=r<len(self.phases)-1: self.phases[r+1],self.phases[r]=self.phases[r],self.phases[r+1]; self._refresh_table(); self.table.selectRow(r+1)

    def del_phase(self):
        r=self._sel()
        if r!=-1: self.phases.pop(r); self._refresh_table()

    # ---------- manual modes ----------
    def _manual_mode(self, m: str):
        if not self.port: self._toast("Connect first"); return
        if hasattr(self,'runner') and self.runner and self.runner.isRunning():
            self._toast("Manual disabled during run"); return
        try:
            self.port.reset_input_buffer()
            self.port.write(f"MODE={m}\n".encode("ascii"))
            self._beep_3s()  # beep on manual action
            t0=time.time(); ack=""
            while time.time()-t0 < 0.3:
                if self.port.in_waiting:
                    ack=self.port.readline().decode(errors="ignore").strip(); break
                time.sleep(0.01)
            self.log.appendPlainText(f"[{now_hms()}] MANUAL MODE={m} {('['+ack+']') if ack else ''}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Serial",str(e))

    # ---------- serial ----------
    def connect_port(self):
        if self.port:
            try:self.port.close()
            except Exception: pass
            self.port=None
        try:
            self.port = serial.Serial(self.portBox.currentText(), BAUD, timeout=0.15)
            time.sleep(0.3); self._drain()
            try:
                self.port.reset_input_buffer()
                self.port.write(b"PING\n")
                line=self.port.readline().decode(errors="ignore").strip()
            except Exception:
                line=""
            self.status.setText(f"Connected {self.port.portstr} @ {BAUD} ({line or 'no echo'})")
            self.sb.showMessage("Connected",3000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Serial",str(e))
            self.status.setText("Disconnected")

    def _drain(self):
        if not self.port: return
        try:
            while self.port.in_waiting: self.port.readline()
        except Exception: pass

    # ---------- run control ----------
    def start_run(self):
        if not self.port: self._toast("Connect first"); return
        if not self.phases: self._toast("Add at least one phase"); return
        if any(p.side=='R' for p in self.phases) and not self.rnd: self._toast("Load random file"); return
        if hasattr(self,'runner') and self.runner and self.runner.isRunning(): self._toast("Run already in progress"); return

        self.expName=self.expEdit.text().strip()
        self.log.clear()
        if self.expName: self.log.appendPlainText(f"[{now_hms()}] Experiment: {self.expName}")
        self.status.setText("Running"); self.curPhaseLbl.setText("Starting…"); self.progressBar.setValue(0)
        self._set_running_ui(True)

        self.runner=Runner(self.port,self.phases,self.rnd,self.expName)
        self.runner.header.connect(lambda s:self._log(s))
        self.runner.log.connect(lambda s:self._log("  "+s))
        self.runner.status.connect(self.status.setText)
        self.runner.currentPhase.connect(self.curPhaseLbl.setText)
        self.runner.progress.connect(self.progressBar.setValue)
        self.runner.beep.connect(self._beep_3s)
        self.runner.done.connect(self._on_done)
        self.runner.start()

    def stop_run(self):
        if hasattr(self,'runner') and self.runner and self.runner.isRunning():
            if QtWidgets.QMessageBox.question(self,"Stop","Stop the run now?") != QtWidgets.QMessageBox.Yes: return
            self.runner.stop(); self.runner.wait(1000)
        try:
            if self.port: self.port.write(b"MODE=N\n")
        except Exception: pass
        self.status.setText("Stopped"); self.curPhaseLbl.setText("Idle"); self.progressBar.setValue(0)
        self._log(f"[{now_hms()}] ===== RUN STOPPED BY USER =====")
        self._set_running_ui(False)

    def _on_done(self): self._set_running_ui(False)

    # ---------- beep ----------
    def _beep_3s(self, *args):
        def _worker():
            try:
                if os.name=="nt":
                    import winsound; winsound.Beep(2000,3000)
                else:
                    t_end=time.time()+3.0
                    while time.time()<t_end:
                        QtWidgets.QApplication.beep(); time.sleep(0.12)
            except Exception: pass
        threading.Thread(target=_worker,daemon=True).start()

    # ---------- random loader ----------
    # Lines: "U 20", "D 13", "A 7", "N 5"  (optional header "state duration")
    def load_random_seq(self):
        path,_=QtWidgets.QFileDialog.getOpenFileName(self,"Random file",".","Text/CSV (*.txt *.csv)")
        if not path: return
        try:
            raw=[]
            with open(path,"r",encoding="utf-8") as f:
                header=False
                for ln in f:
                    s=ln.strip()
                    if not s or s.startswith("#"): continue
                    if not header and ("state" in s and "duration" in s): header=True; continue
                    parts=s.replace(","," ").split()
                    if len(parts)!=2: continue
                    side=parts[0][0].upper()
                    if side not in ("U","D","A","N"): continue
                    ms=int(float(parts[1]))*1000
                    raw.append((ms,side))
            merged=[]
            for ms,side in raw:
                if merged and merged[-1][1]==side: merged[-1]=(merged[-1][0]+ms,side)
                else: merged.append((ms,side))
            self.rnd_raw=raw; self.rnd=merged
            self._toast(f"Random loaded: {len(raw)}→{len(merged)} steps")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self,"Parse error",str(e))

    # ---------- misc ----------
    def _log(self,s): self.log.appendPlainText(s)
    def _toast(self,msg): self.sb.showMessage(msg,2500)

    def showEvent(self,e):
        super().showEvent(e)
        geo = QtWidgets.QStyle.alignedRect(QtCore.Qt.LeftToRight, QtCore.Qt.AlignCenter, self.size(),
                                           QtWidgets.QApplication.primaryScreen().availableGeometry())
        self.setGeometry(geo)

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationDisplayName("Shock Controller — Compact")
    gui = ShockGUI(); gui.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
