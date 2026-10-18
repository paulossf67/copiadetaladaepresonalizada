import sys
import json
from pathlib import Path
from datetime import datetime
from threading import Thread
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton,
    QProgressBar, QMessageBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QComboBox, QTextEdit, QFrame, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont
import psutil

from copy_service import CopyService


class ProgressSignals(QObject):
    progress = pyqtSignal(dict)
    progress_move = pyqtSignal(dict)
    error = pyqtSignal(str, str)
    error_move = pyqtSignal(str, str)
    completed = pyqtSignal()
    completed_move = pyqtSignal()


class CopyWorker(Thread):
    def __init__(self, copy_service, source, destination, signals):
        super().__init__()
        self.copy_service = copy_service
        self.source = source
        self.destination = destination
        self.signals = signals
        self.daemon = True

    def run(self):
        result = self.copy_service.copy_with_progress(self.source, self.destination)
        if result["status"] != "error":
            self.signals.progress.emit(result)
        else:
            self.signals.error.emit("Erro", result["message"])
        self.signals.completed.emit()


class MoveWorker(Thread):
    def __init__(self, copy_service, source, destination, signals):
        super().__init__()
        self.copy_service = copy_service
        self.source = source
        self.destination = destination
        self.signals = signals
        self.daemon = True

    def run(self):
        result = self.copy_service.move_with_progress(self.source, self.destination)
        if result["status"] != "error":
            self.signals.progress_move.emit(result)
        else:
            self.signals.error_move.emit("Erro", result["message"])
        self.signals.completed_move.emit()


class CopyAssistantPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.copy_service = CopyService()
        self.signals = ProgressSignals()
        self.signals.progress.connect(self.on_copy_progress)
        self.signals.error.connect(self.on_copy_error)
        self.signals.completed.connect(self.on_copy_completed)
        self.signals.progress_move.connect(self.on_move_progress)
        self.signals.error_move.connect(self.on_move_error)
        self.signals.completed_move.connect(self.on_move_completed)
        self.current_operation = None
        self.operation_queue = []
        self.queue_running = False
        self.init_ui()
        self.start_system_stats_timer()

    def init_ui(self):
        self.setWindowTitle("Copy Assistant Pro")
        self.setGeometry(100, 100, 1000, 700)
        self.setFont(QFont("Segoe UI", 10))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        navbar = self.create_navbar()
        layout.addWidget(navbar)

        tabs = QTabWidget()
        tabs.addTab(self.create_copy_tab(), "📋 Copiar Arquivos")
        tabs.addTab(self.create_move_tab(), "📦 Mover Arquivos")
        tabs.addTab(self.create_queue_tab(), "⚙️ Fila de Operações")
        tabs.addTab(self.create_check_tab(), "🔍 Verificar Acesso")
        tabs.addTab(self.create_history_tab(), "📜 Histórico")
        tabs.addTab(self.create_settings_tab(), "⚙️ Configurações")
        layout.addWidget(tabs)

        self.apply_theme()

    def create_navbar(self) -> QFrame:
        navbar = QFrame()
        navbar.setStyleSheet("background-color: #2c3e50; color: white; padding: 10px;")
        layout = QHBoxLayout(navbar)

        title = QLabel("📋 Copy Assistant Pro")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)

        layout.addStretch()

        self.cpu_label = QLabel("CPU: --")
        self.cpu_label.setStyleSheet("color: #3498db;")
        self.mem_label = QLabel("MEM: --")
        self.mem_label.setStyleSheet("color: #2ecc71;")
        self.disk_label = QLabel("DISK: --")
        self.disk_label.setStyleSheet("color: #e74c3c;")

        layout.addWidget(self.cpu_label)
        layout.addWidget(self.mem_label)
        layout.addWidget(self.disk_label)

        return navbar

    def create_copy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Caminho de Origem:"))
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("C:\\Users\\...\\Documentos")
        self.source_input.textChanged.connect(self.validate_source)
        source_layout = QHBoxLayout()
        source_layout.addWidget(self.source_input)
        layout.addLayout(source_layout)

        self.source_info = QLabel("")
        self.source_info.setStyleSheet("color: #27ae60; font-size: 9pt;")
        layout.addWidget(self.source_info)

        layout.addWidget(QLabel("Caminho de Destino:"))
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("C:\\Backup\\...")
        self.dest_input.textChanged.connect(self.validate_dest)
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(self.dest_input)
        layout.addLayout(dest_layout)

        self.dest_info = QLabel("")
        self.dest_info.setStyleSheet("color: #27ae60; font-size: 9pt;")
        layout.addWidget(self.dest_info)

        self.btn_start = QPushButton("▶ Iniciar Cópia")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.btn_start.clicked.connect(self.start_copy)
        layout.addWidget(self.btn_start)

        control_layout = QHBoxLayout()
        self.btn_pause = QPushButton("⏸️ Pausar")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("QPushButton { background-color: #f39c12; color: white; padding: 8px; border-radius: 5px; } QPushButton:disabled { background-color: #bdc3c7; }")
        self.btn_pause.clicked.connect(self.pause_copy)
        control_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("⏹️ Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; padding: 8px; border-radius: 5px; } QPushButton:disabled { background-color: #bdc3c7; }")
        self.btn_cancel.clicked.connect(self.cancel_copy)
        control_layout.addWidget(self.btn_cancel)
        layout.addLayout(control_layout)

        layout.addWidget(QLabel("Progresso:"))
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.progress_info = QLabel("")
        self.progress_info.setStyleSheet("color: #34495e; font-size: 9pt;")
        layout.addWidget(self.progress_info)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #2c3e50; font-size: 9pt;")
        layout.addWidget(self.stats_label)

        layout.addWidget(QLabel("📂 Arquivos em Progresso:"))
        self.files_list = QListWidget()
        self.files_list.setMaximumHeight(120)
        layout.addWidget(self.files_list)

        layout.addStretch()
        return widget

    def create_move_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Caminho de Origem:"))
        self.move_source_input = QLineEdit()
        self.move_source_input.setPlaceholderText("C:\\Users\\...\\Documentos")
        self.move_source_input.textChanged.connect(self.validate_move_source)
        move_src_layout = QHBoxLayout()
        move_src_layout.addWidget(self.move_source_input)
        layout.addLayout(move_src_layout)

        self.move_source_info = QLabel("")
        self.move_source_info.setStyleSheet("color: #27ae60; font-size: 9pt;")
        layout.addWidget(self.move_source_info)

        layout.addWidget(QLabel("Caminho de Destino:"))
        self.move_dest_input = QLineEdit()
        self.move_dest_input.setPlaceholderText("C:\\Backup\\...")
        self.move_dest_input.textChanged.connect(self.validate_move_dest)
        move_dst_layout = QHBoxLayout()
        move_dst_layout.addWidget(self.move_dest_input)
        layout.addLayout(move_dst_layout)

        self.move_dest_info = QLabel("")
        self.move_dest_info.setStyleSheet("color: #27ae60; font-size: 9pt;")
        layout.addWidget(self.move_dest_info)

        self.btn_start_move = QPushButton("📦 Iniciar Movimento")
        self.btn_start_move.setStyleSheet("QPushButton { background-color: #e67e22; color: white; padding: 10px; border-radius: 5px; font-weight: bold; } QPushButton:hover { background-color: #d35400; }")
        self.btn_start_move.clicked.connect(self.start_move)
        layout.addWidget(self.btn_start_move)

        move_control_layout = QHBoxLayout()
        self.btn_pause_move = QPushButton("⏸️ Pausar")
        self.btn_pause_move.setEnabled(False)
        self.btn_pause_move.setStyleSheet("QPushButton { background-color: #f39c12; color: white; padding: 8px; border-radius: 5px; } QPushButton:disabled { background-color: #bdc3c7; }")
        self.btn_pause_move.clicked.connect(self.pause_move)
        move_control_layout.addWidget(self.btn_pause_move)

        self.btn_cancel_move = QPushButton("⏹️ Cancelar")
        self.btn_cancel_move.setEnabled(False)
        self.btn_cancel_move.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; padding: 8px; border-radius: 5px; } QPushButton:disabled { background-color: #bdc3c7; }")
        self.btn_cancel_move.clicked.connect(self.cancel_move)
        move_control_layout.addWidget(self.btn_cancel_move)
        layout.addLayout(move_control_layout)

        layout.addWidget(QLabel("Progresso:"))
        self.move_progress_bar = QProgressBar()
        layout.addWidget(self.move_progress_bar)

        self.move_progress_info = QLabel("")
        self.move_progress_info.setStyleSheet("color: #34495e; font-size: 9pt;")
        layout.addWidget(self.move_progress_info)

        self.move_stats_label = QLabel("")
        self.move_stats_label.setStyleSheet("color: #2c3e50; font-size: 9pt;")
        layout.addWidget(self.move_stats_label)

        layout.addWidget(QLabel("📂 Arquivos em Progresso:"))
        self.move_files_list = QListWidget()
        self.move_files_list.setMaximumHeight(120)
        layout.addWidget(self.move_files_list)

        layout.addStretch()
        return widget

    def create_queue_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Tipo de Operação:"))
        type_layout = QHBoxLayout()
        self.queue_copy_btn = QRadioButton("Copiar")
        self.queue_move_btn = QRadioButton("Mover")
        self.queue_copy_btn.setChecked(True)
        type_layout.addWidget(self.queue_copy_btn)
        type_layout.addWidget(self.queue_move_btn)
        layout.addLayout(type_layout)

        layout.addWidget(QLabel("Caminho de Origem:"))
        self.queue_source_input = QLineEdit()
        self.queue_source_input.setPlaceholderText("C:\\Users\\...\\Documentos")
        queue_src_layout = QHBoxLayout()
        queue_src_layout.addWidget(self.queue_source_input)
        layout.addLayout(queue_src_layout)

        layout.addWidget(QLabel("Caminho de Destino:"))
        self.queue_dest_input = QLineEdit()
        self.queue_dest_input.setPlaceholderText("C:\\Backup\\...")
        queue_dst_layout = QHBoxLayout()
        queue_dst_layout.addWidget(self.queue_dest_input)
        layout.addLayout(queue_dst_layout)

        self.queue_verify_checkbox = QCheckBox("Verificar integridade após cópia")
        self.queue_verify_checkbox.setChecked(True)
        layout.addWidget(self.queue_verify_checkbox)

        btn_add_queue = QPushButton("➕ Adicionar à Fila")
        btn_add_queue.setStyleSheet("QPushButton { background-color: #16a085; color: white; padding: 10px; border-radius: 5px; } QPushButton:hover { background-color: #138d75; }")
        btn_add_queue.clicked.connect(self.add_to_queue)
        layout.addWidget(btn_add_queue)

        layout.addWidget(QLabel("Fila de Operações:"))
        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)

        queue_control_layout = QHBoxLayout()
        btn_start_queue = QPushButton("▶ Iniciar Fila")
        btn_start_queue.setStyleSheet("QPushButton { background-color: #3498db; color: white; padding: 8px; border-radius: 5px; }")
        btn_start_queue.clicked.connect(self.start_queue)
        queue_control_layout.addWidget(btn_start_queue)

        btn_remove_queue = QPushButton("🗑️ Remover")
        btn_remove_queue.clicked.connect(self.remove_from_queue)
        queue_control_layout.addWidget(btn_remove_queue)

        btn_clear_queue = QPushButton("⚠️ Limpar Fila")
        btn_clear_queue.clicked.connect(self.clear_queue)
        queue_control_layout.addWidget(btn_clear_queue)

        layout.addLayout(queue_control_layout)
        layout.addStretch()
        return widget

    def create_check_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Arquivo para Verificar:"))
        self.check_input = QLineEdit()
        self.check_input.setPlaceholderText("C:\\Users\\...\\arquivo.txt")
        check_layout = QHBoxLayout()
        check_layout.addWidget(self.check_input)
        layout.addLayout(check_layout)

        btn_check = QPushButton("🔍 Verificar Leitura")
        btn_check.setStyleSheet("QPushButton { background-color: #27ae60; color: white; padding: 10px; border-radius: 5px; font-weight: bold; }")
        btn_check.clicked.connect(self.check_file_access)
        layout.addWidget(btn_check)

        self.check_result = QTextEdit()
        self.check_result.setReadOnly(True)
        layout.addWidget(self.check_result)

        layout.addStretch()
        return widget

    def create_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.clicked.connect(self.load_history)
        layout.addWidget(btn_refresh)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(["Data/Hora", "Origem", "Destino", "Arquivos", "Tamanho (MB)", "Velocidade (MB/s)"])
        layout.addWidget(self.history_table)

        layout.addStretch()
        return widget

    def create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("Notificações:"))
        self.notify_completion = QCheckBox("Notificar ao concluir cópia")
        self.notify_completion.setChecked(True)
        layout.addWidget(self.notify_completion)

        self.notify_errors = QCheckBox("Notificar erros durante cópia")
        self.notify_errors.setChecked(True)
        layout.addWidget(self.notify_errors)

        layout.addWidget(QLabel("\nComportamento:"))
        self.preserve_timestamps = QCheckBox("Preservar data/hora dos arquivos")
        self.preserve_timestamps.setChecked(True)
        layout.addWidget(self.preserve_timestamps)

        self.auto_clear = QCheckBox("Limpar formulário após cópia")
        self.auto_clear.setChecked(True)
        layout.addWidget(self.auto_clear)

        layout.addWidget(QLabel("\nAparência:"))
        layout.addWidget(QLabel("Tema:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Claro", "Escuro", "Automático"])
        self.theme_combo.currentTextChanged.connect(lambda: self.apply_theme())
        layout.addWidget(self.theme_combo)

        btn_save = QPushButton("💾 Salvar Configurações")
        btn_save.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; padding: 10px; border-radius: 5px; }")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)

        layout.addStretch()
        return widget

    def browse_source(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de origem")
        if path:
            self.source_input.setText(path)

    def browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if path:
            self.dest_input.setText(path)

    def browse_move_source(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de origem")
        if path:
            self.move_source_input.setText(path)

    def browse_move_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if path:
            self.move_dest_input.setText(path)

    def browse_queue_source(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de origem")
        if path:
            self.queue_source_input.setText(path)

    def browse_queue_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta de destino")
        if path:
            self.queue_dest_input.setText(path)

    def browse_check_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecione um arquivo")
        if path:
            self.check_input.setText(path)

    def validate_source(self):
        path = self.source_input.text().strip()
        if path:
            info = self.copy_service.get_path_info(path)
            if info["valid"]:
                if info["type"] == "directory":
                    self.source_info.setText(f"✓ {info['file_count']} arquivo(s) | {info['size_mb']} MB")
                else:
                    self.source_info.setText(f"✓ {info['size_mb']} MB")
            else:
                self.source_info.setText("✗ Caminho não encontrado")
                self.source_info.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        else:
            self.source_info.setText("")

    def validate_dest(self):
        path = self.dest_input.text().strip()
        if path:
            info = self.copy_service.get_path_info(path)
            if info["valid"]:
                self.dest_info.setText("✓ Caminho válido")
            else:
                self.dest_info.setText("⚠ Caminho será criado")
                self.dest_info.setStyleSheet("color: #f39c12; font-size: 9pt;")
        else:
            self.dest_info.setText("")

    def validate_move_source(self):
        path = self.move_source_input.text().strip()
        if path:
            info = self.copy_service.get_path_info(path)
            if info["valid"]:
                if info["type"] == "directory":
                    self.move_source_info.setText(f"✓ {info['file_count']} arquivo(s) | {info['size_mb']} MB")
                else:
                    self.move_source_info.setText(f"✓ {info['size_mb']} MB")
            else:
                self.move_source_info.setText("✗ Caminho não encontrado")
                self.move_source_info.setStyleSheet("color: #e74c3c; font-size: 9pt;")
        else:
            self.move_source_info.setText("")

    def validate_move_dest(self):
        path = self.move_dest_input.text().strip()
        if path:
            info = self.copy_service.get_path_info(path)
            if info["valid"]:
                self.move_dest_info.setText("✓ Caminho válido")
            else:
                self.move_dest_info.setText("⚠ Caminho será criado")
                self.move_dest_info.setStyleSheet("color: #f39c12; font-size: 9pt;")
        else:
            self.move_dest_info.setText("")

    def add_to_queue(self):
        source = self.queue_source_input.text().strip()
        dest = self.queue_dest_input.text().strip()
        is_move = self.queue_move_btn.isChecked()

        if not source or not dest:
            QMessageBox.warning(self, "Erro", "Preencha origem e destino")
            return

        info = self.copy_service.get_path_info(source)
        if not info["valid"]:
            QMessageBox.warning(self, "Erro", "Caminho de origem inválido")
            return

        op_type = "Mover" if is_move else "Copiar"
        item_text = f"{op_type} | {Path(source).name} → {Path(dest).name}"

        operation = {
            "type": "move" if is_move else "copy",
            "source": source,
            "destination": dest,
            "verify": self.queue_verify_checkbox.isChecked(),
            "status": "pendente"
        }

        self.operation_queue.append(operation)
        self.queue_list.addItem(item_text)
        self.queue_source_input.clear()
        self.queue_dest_input.clear()
        QMessageBox.information(self, "Sucesso", "Operação adicionada à fila!")

    def remove_from_queue(self):
        current_row = self.queue_list.currentRow()
        if current_row >= 0:
            self.queue_list.takeItem(current_row)
            self.operation_queue.pop(current_row)

    def clear_queue(self):
        reply = QMessageBox.question(self, "Confirmar", "Limpar toda a fila?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.queue_list.clear()
            self.operation_queue.clear()

    def start_queue(self):
        if not self.operation_queue:
            QMessageBox.warning(self, "Erro", "Fila vazia!")
            return

        if self.queue_running:
            QMessageBox.warning(self, "Erro", "Fila já está em execução!")
            return

        self.queue_running = True
        self.process_next_queue_item()

    def process_next_queue_item(self):
        if not self.operation_queue or not self.queue_running:
            self.queue_running = False
            QMessageBox.information(self, "Sucesso", "Fila processada completamente!")
            return

        operation = self.operation_queue.pop(0)
        self.queue_list.takeItem(0)

        if operation["type"] == "copy":
            self.source_input.setText(operation["source"])
            self.dest_input.setText(operation["destination"])
            self.current_operation = CopyWorker(self.copy_service, operation["source"], operation["destination"], self.signals)
            self.current_operation.start()
        else:
            self.move_source_input.setText(operation["source"])
            self.move_dest_input.setText(operation["destination"])
            self.current_operation = MoveWorker(self.copy_service, operation["source"], operation["destination"], self.signals)
            self.current_operation.start()

    def start_copy(self):
        source = self.source_input.text().strip()
        dest = self.dest_input.text().strip()

        if not source or not dest:
            QMessageBox.warning(self, "Erro", "Preencha origem e destino")
            return

        info = self.copy_service.get_path_info(source)
        if not info["valid"]:
            QMessageBox.warning(self, "Erro", "Caminho de origem inválido")
            return

        self.copy_service.reset_flags()
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_info.setText("")
        self.stats_label.setText("")

        self.current_operation = CopyWorker(self.copy_service, source, dest, self.signals)
        self.current_operation.start()

    def start_move(self):
        source = self.move_source_input.text().strip()
        dest = self.move_dest_input.text().strip()

        if not source or not dest:
            QMessageBox.warning(self, "Erro", "Preencha origem e destino")
            return

        info = self.copy_service.get_path_info(source)
        if not info["valid"]:
            QMessageBox.warning(self, "Erro", "Caminho de origem inválido")
            return

        reply = QMessageBox.question(self, "Confirmar Movimento", f"Você tem certeza que deseja MOVER:\n\n{source}\n\npara\n\n{dest}\n\nA origem será DELETADA após a cópia.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            return

        self.copy_service.reset_flags()
        self.btn_start_move.setEnabled(False)
        self.btn_pause_move.setEnabled(True)
        self.btn_cancel_move.setEnabled(True)
        self.move_progress_bar.setValue(0)
        self.move_progress_info.setText("")
        self.move_stats_label.setText("")

        self.current_operation = MoveWorker(self.copy_service, source, dest, self.signals)
        self.current_operation.start()

    def pause_copy(self):
        if self.copy_service.is_paused:
            self.copy_service.resume()
            self.btn_pause.setText("⏸️ Pausar")
        else:
            self.copy_service.pause()
            self.btn_pause.setText("▶️ Retomar")

    def cancel_copy(self):
        reply = QMessageBox.question(self, "Confirmar", "Cancelar operação?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.copy_service.cancel()
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            self.btn_pause.setText("⏸️ Pausar")

    def pause_move(self):
        if self.copy_service.is_paused:
            self.copy_service.resume()
            self.btn_pause_move.setText("⏸️ Pausar")
        else:
            self.copy_service.pause()
            self.btn_pause_move.setText("▶️ Retomar")

    def cancel_move(self):
        reply = QMessageBox.question(self, "Confirmar", "Cancelar movimento?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.copy_service.cancel()
            self.btn_start_move.setEnabled(True)
            self.btn_pause_move.setEnabled(False)
            self.btn_cancel_move.setEnabled(False)
            self.btn_pause_move.setText("⏸️ Pausar")

    def on_copy_progress(self, data):
        if "progress_percent" in data:
            self.progress_bar.setValue(int(data["progress_percent"]))
        if "current_file" in data:
            self.progress_info.setText(f"Arquivo: {data['current_file']} | Velocidade: {data['speed_mbps']} MB/s | Tempo: {data['elapsed_time']}s")
            self.files_list.insertItem(0, f"✓ {data['current_file']}")
            if self.files_list.count() > 10:
                self.files_list.takeItem(self.files_list.count() - 1)

        if "files_copied" in data:
            bytes_copied_mb = data['bytes_copied'] / (1024*1024)
            total_bytes_mb = data['total_bytes'] / (1024*1024)
            self.stats_label.setText(f"Arquivos: {data['files_copied']}/{data['total_files']} | Tamanho: {bytes_copied_mb:.2f}/{total_bytes_mb:.2f} MB")

    def on_copy_error(self, title, message):
        QMessageBox.critical(self, title, message)
        self.btn_start.setEnabled(True)

    def on_copy_completed(self):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_pause.setText("⏸️ Pausar")
        self.copy_service.reset_flags()

        source = self.source_input.text().strip()
        dest = self.dest_input.text().strip()

        msg = "Cópia concluída!"
        if source and dest:
            result = self.copy_service.verify_copy_integrity(source, dest)
            if result["status"] == "completed":
                if result["failed"] == 0:
                    msg += f"\n✓ Verificação de integridade: OK ({result['verified']} arquivos)"
                else:
                    msg += f"\n⚠️ {result['failed']} arquivo(s) corrompido(s)!"

        QMessageBox.information(self, "Sucesso", msg)
        if self.auto_clear.isChecked():
            self.source_input.clear()
            self.dest_input.clear()

        self.files_list.clear()
        self.load_history()

    def on_move_progress(self, data):
        if "progress_percent" in data:
            self.move_progress_bar.setValue(int(data["progress_percent"]))
        if "current_file" in data:
            self.move_progress_info.setText(f"Arquivo: {data['current_file']} | Velocidade: {data['speed_mbps']} MB/s | Tempo: {data['elapsed_time']}s")
            self.move_files_list.insertItem(0, f"✓ {data['current_file']}")
            if self.move_files_list.count() > 10:
                self.move_files_list.takeItem(self.move_files_list.count() - 1)

        if "files_copied" in data:
            bytes_copied_mb = data['bytes_copied'] / (1024*1024)
            total_bytes_mb = data['total_bytes'] / (1024*1024)
            self.move_stats_label.setText(f"Arquivos: {data['files_copied']}/{data['total_files']} | Tamanho: {bytes_copied_mb:.2f}/{total_bytes_mb:.2f} MB")

    def on_move_error(self, title, message):
        QMessageBox.critical(self, title, message)
        self.btn_start_move.setEnabled(True)

    def on_move_completed(self):
        self.btn_start_move.setEnabled(True)
        self.btn_pause_move.setEnabled(False)
        self.btn_cancel_move.setEnabled(False)
        self.btn_pause_move.setText("⏸️ Pausar")
        self.copy_service.reset_flags()

        QMessageBox.information(self, "Sucesso", "Movimento concluído! A origem foi deletada.")
        if self.auto_clear.isChecked():
            self.move_source_input.clear()
            self.move_dest_input.clear()

        self.move_files_list.clear()
        self.load_history()

    def check_file_access(self):
        file_path = self.check_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Erro", "Informe um caminho de arquivo")
            return

        result = self.copy_service.check_file_access(file_path)
        if result["status"] == "accessible":
            size_mb = result['size'] / (1024*1024)
            self.check_result.setText(f"✓ Arquivo acessível\n\nNome: {result['file']}\nTamanho: {size_mb:.2f} MB\n\nO arquivo pode ser lido por completo.")
            self.check_result.setStyleSheet("color: #27ae60; background-color: #d5f4e6;")
        else:
            self.check_result.setText(f"✗ Arquivo inacessível\n\nErro: {result.get('message', result.get('error', 'Desconhecido'))}")
            self.check_result.setStyleSheet("color: #e74c3c; background-color: #fadbd8;")

    def load_history(self):
        history = self.copy_service.get_history()
        self.history_table.setRowCount(len(history))

        for row, record in enumerate(reversed(history)):
            items = [record.get("timestamp", ""), record.get("source", ""), record.get("destination", ""), str(record.get("files_copied", 0)), str(record.get("size_mb", 0)), str(record.get("speed_mbps", 0))]
            for col, item_text in enumerate(items):
                item = QTableWidgetItem(item_text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, col, item)

    def save_settings(self):
        config = {
            "notify_completion": self.notify_completion.isChecked(),
            "notify_errors": self.notify_errors.isChecked(),
            "preserve_timestamps": self.preserve_timestamps.isChecked(),
            "auto_clear": self.auto_clear.isChecked(),
            "theme": self.theme_combo.currentText()
        }
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        QMessageBox.information(self, "Sucesso", "Configurações salvas!")

    def apply_theme(self):
        theme = self.theme_combo.currentText()
        if theme == "Escuro":
            self.setStyleSheet("QMainWindow { background-color: #1e1e1e; color: white; } QLineEdit, QTextEdit, QTableWidget { background-color: #2d2d2d; color: white; border: 1px solid #3d3d3d; } QLabel { color: white; }")
        else:
            self.setStyleSheet("QMainWindow { background-color: #ffffff; color: #2c3e50; } QLineEdit, QTextEdit, QTableWidget { background-color: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7; } QLabel { color: #2c3e50; }")

    def update_system_stats(self):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        self.cpu_label.setText(f"CPU: {cpu:.1f}%")
        self.mem_label.setText(f"MEM: {mem.percent:.1f}%")
        self.disk_label.setText(f"DISK: {disk.percent:.1f}%")

    def start_system_stats_timer(self):
        timer = QTimer()
        timer.timeout.connect(self.update_system_stats)
        timer.start(2000)
        self.update_system_stats()


def main():
    app = QApplication(sys.argv)
    window = CopyAssistantPro()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
