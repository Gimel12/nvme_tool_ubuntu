import sys
import subprocess
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QHBoxLayout, QLabel, QCheckBox, QTextEdit
from PyQt5.QtCore import QTimer

class NVMeDriveItem(QWidget):
    def __init__(self, drive_info):
        super().__init__()
        layout = QHBoxLayout(self)

        self.checkbox = QCheckBox()
        self.label = QLabel(drive_info)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)

    def isChecked(self):
        return self.checkbox.isChecked()

    def getDriveNode(self):
        return self.label.text().split('|')[0].strip()

class NVMeTool(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("NVMe Tool")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()
        self.driveList = QListWidget()
        self.refreshButton = QPushButton("List NVMe Drives")
        self.benchmarkButton = QPushButton("Start Benchmark")
        self.stopButton = QPushButton("Stop Benchmark")
        self.metricsButton = QPushButton("Start Metrics")
        self.metricsDisplay = QTextEdit()

        layout.addWidget(self.driveList)
        layout.addWidget(self.refreshButton)
        layout.addWidget(self.benchmarkButton)
        layout.addWidget(self.stopButton)
        layout.addWidget(self.metricsButton)
        layout.addWidget(self.metricsDisplay)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.refreshButton.clicked.connect(self.refreshNVMeList)
        self.benchmarkButton.clicked.connect(self.runBenchmark)
        self.stopButton.clicked.connect(self.stopBenchmark)
        self.metricsButton.clicked.connect(self.startMetrics)

        self.benchmark_processes = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateMetrics)
        self.timer.setInterval(10000)  # 10 seconds

    def refreshNVMeList(self):
        self.driveList.clear()
        nvme_info = self.getNVMeList()
        for drive in nvme_info:
            item = QListWidgetItem(self.driveList)
            widget = NVMeDriveItem(drive)
            item.setSizeHint(widget.sizeHint())
            self.driveList.addItem(item)
            self.driveList.setItemWidget(item, widget)

    def getNVMeList(self):
        try:
            result = subprocess.run(["sudo", "nvme", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout
            lines = output.split('\n')
            drives = []
            for line in lines[2:]:  # Skip header lines
                if line.strip():
                    parts = line.split()
                    node = parts[0]
                    sn = parts[1]
                    model = parts[2]
                    usage = parts[4] + " / " + parts[6]
                    drives.append(f"{node} | {sn} | {model} | {usage}")
            return drives
        except Exception as e:
            print(f"Error: {e}")
            return []

    def runBenchmark(self):
        for index in range(self.driveList.count()):
            item = self.driveList.item(index)
            widget = self.driveList.itemWidget(item)
            if widget.isChecked():
                drive_node = widget.getDriveNode()
                thread = threading.Thread(target=self.benchmarkDrive, args=(drive_node,))
                thread.start()
                self.benchmark_processes.append(thread)

    def benchmarkDrive(self, drive_node):
        command = ["sudo", "dd", "if=/dev/zero", f"of={drive_node}", "bs=1000M", "oflag=direct", "status=progress"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)

        for line in iter(process.stdout.readline, ''):
            if "bytes transferred" in line:
                speed_info = line.split(",")[-2].strip()  # Assuming the speed info is the second last element
                self.updateBenchmarkMetrics(drive_node, speed_info)

        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(f"Benchmark completed for {drive_node}")
        else:
            print(f"Error running benchmark on {drive_node}: {stderr}")

    def updateBenchmarkMetrics(self, drive_node, speed_info):
        self.metricsDisplay.append(f"{drive_node} Speed: {speed_info}\n")

    def stopBenchmark(self):
        for process in self.benchmark_processes:
            if process.is_alive():
                process.terminate()
        self.benchmark_processes.clear()

    def startMetrics(self):
        self.timer.start()

    def updateMetrics(self):
        self.metricsDisplay.clear()
        for index in range(self.driveList.count()):
            item = self.driveList.item(index)
            widget = self.driveList.itemWidget(item)
            if widget.isChecked():
                drive_node = widget.getDriveNode()
                metrics = self.getDriveMetrics(drive_node)
                self.metricsDisplay.append(f"{drive_node} Metrics:\n{metrics}\n")

    def getDriveMetrics(self, drive_node):
        command = ["sudo", "nvme", "smart-log", drive_node]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout
            metrics = ""
            for line in output.split('\n'):
                if "temperature" in line or "critical_warning" in line:
                    metrics += line + '\n'
            return metrics
        except Exception as e:
            return f"Error fetching metrics for {drive_node}: {e}"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = NVMeTool()
    mainWin.show()
    sys.exit(app.exec_())
