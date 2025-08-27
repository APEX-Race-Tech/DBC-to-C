import sys
import os
import cantools
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTextEdit, QLabel, QStatusBar, QMessageBox,
    QSplitter
)
from PyQt5.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QIcon
from PyQt5.QtCore import Qt, QUrl, QSize
from PyQt5.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QIcon, QPixmap, QCursor, QPainter
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTextEdit, QLabel, QStatusBar, QMessageBox,
    QSplitter, QDialog, QTabWidget, QTableWidget, QListWidget, QFrame,
    QTableWidgetItem, QListWidgetItem, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import pyqtSignal

# --- C Syntax Highlighting (A simple version for portability) ---
class CppHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "\\bchar\\b", "\\bclass\\b", "\\bconst\\b", "\\bdouble\\b", "\\benum\\b",
            "\\bfloat\\b", "\\bint\\b", "\\blong\\b", "\\bshort\\b", "\\bsigned\\b",
            "\\bstruct\\b", "\\btypedef\\b", "\\bunion\\b", "\\bunsigned\\b", "\\bvoid\\b",
            "\\bvolatile\\b", "\\bif\\b", "\\belse\\b", "\\bfor\\b", "\\bwhile\\b",
            "\\breturn\\b", "\\bcase\\b", "\\bswitch\\b", "\\bbreak\\b", "\\bcontinue\\b",
            "\\bstatic\\b", "\\bextern\\b"
        ]
        for word in keywords:
            self.highlighting_rules.append((f"\\b{word}\\b", keyword_format))

        # Types (like uint8_t)
        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#4EC9B0"))
        types = ["uint8_t", "uint16_t", "uint32_t", "uint64_t", "int8_t", "int16_t", "int32_t", "int64_t"]
        for t in types:
            self.highlighting_rules.append((f"\\b{t}\\b", type_format))

        # Preprocessor directives
        preprocessor_format = QTextCharFormat()
        preprocessor_format.setForeground(QColor("#C586C0"))
        self.highlighting_rules.append(("#[^\n]*", preprocessor_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append(("//[^\n]*", comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in __import__("re").finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), format)

# --- Bit Layout Viewer Widget ---
class BitLayoutViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.message = None
        self.database = None
        self.bit_to_signal_map = {}
        self.signal_colors = {}
        # A more modern and distinct color palette (Tableau 10)
        self.color_palette = [
            QColor("#4E79A7"), QColor("#F28E2B"), QColor("#E15759"), 
            QColor("#76B7B2"), QColor("#59A14F"), QColor("#EDC948"), 
            QColor("#B07AA1"), QColor("#FF9DA7"), QColor("#9C755F"), 
            QColor("#BAB0AC")
        ]
        
        # --- Main Layout ---
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        # Ensure the viewer expands nicely inside splitters/layouts
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # --- Center Widget for Grid and Header ---
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(10, 10, 10, 10)
        center_layout.setSpacing(5)
        
        # --- Message Selector ---
        message_selector_layout = QHBoxLayout()
        
        # Message count and selector label
        selector_header_layout = QVBoxLayout()
        self.message_count_label = QLabel("No DBC file loaded")
        self.message_count_label.setStyleSheet("font-size: 10pt; color: #aaa; font-weight: normal;")
        selector_header_layout.addWidget(self.message_count_label)
        
        selector_label_layout = QHBoxLayout()
        selector_label_layout.addWidget(QLabel("Select Message:"))
        selector_header_layout.addLayout(selector_label_layout)
        
        message_selector_layout.addLayout(selector_header_layout)
        
        # Add checkbox for multiple selection
        self.multi_select_checkbox = QCheckBox("Multi-Select")
        self.multi_select_checkbox.setStyleSheet("""
            QCheckBox { 
                color: #ccc; 
                font-size: 9pt;
            }
            QCheckBox::indicator { 
                width: 16px; 
                height: 16px; 
            }
        """)
        self.multi_select_checkbox.stateChanged.connect(self._on_multi_select_changed)
        selector_header_layout.addWidget(self.multi_select_checkbox)
        
        self.message_combo = QListWidget()
        self.message_combo.setMaximumHeight(120)
        self.message_combo.setSelectionMode(QListWidget.SingleSelection)
        self.message_combo.setStyleSheet("""
            QListWidget { 
                background-color: #1e1e1e; 
                border: 1px solid #444; 
                border-radius: 4px;
                color: #ccc;
            }
            QListWidget::item { 
                padding: 4px; 
                border-bottom: 1px solid #333; 
            }
            QListWidget::item:selected { 
                background-color: #0078d7; 
                color: white;
            }
            QListWidget::item:hover { 
                background-color: #3c3c3c; 
            }
        """)
        self.message_combo.itemClicked.connect(self._on_message_clicked)
        message_selector_layout.addWidget(self.message_combo)
        
        center_layout.addLayout(message_selector_layout)
        
        self.header_label = QLabel("No Message Selected")
        self.header_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #ddd;")
        
        self.bit_grid = QTableWidget()
        self.bit_grid.setStyleSheet("""
            QTableWidget { gridline-color: #555; background-color: #2b2b2b; }
            QTableWidget::item { padding: 2px; color: #ccc; }
            QTableWidget::item:selected { background-color: #0078d7; }
            QHeaderView::section { background-color: #3c3c3c; padding: 4px; border: 1px solid #555; }
        """)
        center_layout.addWidget(self.header_label)
        center_layout.addWidget(self.bit_grid)

        # --- Right Panel (Signal List) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFixedWidth(280)
        right_panel.setStyleSheet("background-color: #2b2b2b;")
        
        self.signal_list = QListWidget()
        self.signal_list.setStyleSheet("QListWidget::item { border-bottom: 1px solid #444; }")
        self.signal_list.currentItemChanged.connect(self._on_signal_selected)

        right_layout.addWidget(QLabel("Signals"))
        right_layout.addWidget(self.signal_list)
        
        main_layout.addWidget(center_widget, 1) # Add stretch factor
        main_layout.addWidget(right_panel)
    
    def load_database(self, database):
        """Load a DBC database and populate the message selector."""
        self.database = database
        self.message_combo.clear()
        
        if not database or not database.messages:
            self.message_count_label.setText("No DBC file loaded")
            self.message_combo.addItem("No messages available")
            return
        
        # Update message count label
        self.message_count_label.setText(f"Total Messages: {len(database.messages)}")
        
        # Add all messages to the selector
        for message in database.messages:
            frame_id = getattr(message, 'frame_id', None)
            try:
                id_str = f"0x{int(frame_id):X}" if frame_id is not None else "N/A"
            except Exception:
                id_str = "N/A"
            
            item_text = f"{message.name} (ID: {id_str})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, message)
            self.message_combo.addItem(item)
        
        # Select the first message by default and display it
        if self.message_combo.count() > 0:
            self.message_combo.setCurrentRow(0)
            first_item = self.message_combo.item(0)
            if first_item:
                self.display_message(first_item.data(Qt.UserRole))
    
    def _on_multi_select_changed(self, state):
        """Handle multi-select checkbox state change."""
        if state == Qt.Checked:
            self.message_combo.setSelectionMode(QListWidget.MultiSelection)
        else:
            self.message_combo.setSelectionMode(QListWidget.SingleSelection)
            # Clear multiple selections when switching to single mode
            self.message_combo.clearSelection()
    
    def _on_message_clicked(self, item):
        """Handle message click - always show the clicked message in bit viewer."""
        message = item.data(Qt.UserRole)
        if message:
            self.display_message(message)
    
    def get_selected_messages(self):
        """Get list of currently selected messages."""
        selected_items = self.message_combo.selectedItems()
        messages = []
        for item in selected_items:
            message = item.data(Qt.UserRole)
            if message:
                messages.append(message)
        return messages
    
    def display_message(self, message):
        """Public method to load a message into the viewer."""
        self.message = message
        self._generate_bit_map()
        self._populate_signal_list()
        self._populate_grid()
        self._style_grid()

    def _generate_bit_map(self):
        self.bit_to_signal_map.clear()
        if not self.message: return
        for signal in self.message.signals:
            for i in range(signal.length):
                self.bit_to_signal_map[signal.start + i] = signal

    def _populate_signal_list(self):
        self.signal_list.clear()
        self.signal_colors.clear()
        if not self.message: return

        for i, signal in enumerate(self.message.signals):
            color = self.color_palette[i % len(self.color_palette)]
            self.signal_colors[signal.name] = color
            
            details = f"{signal.length}b @ {signal.start}, {'BE' if signal.byte_order == 'big_endian' else 'LE'}"
            item_widget = SignalListItemWidget(color, signal.name, details)
            
            list_item = QListWidgetItem(self.signal_list)
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setData(Qt.UserRole, signal) # Store signal object
            self.signal_list.addItem(list_item)
            self.signal_list.setItemWidget(list_item, item_widget)

    def _populate_grid(self):
        self.bit_grid.clear()
        if not self.message: 
            self.header_label.setText("No Message Selected")
            # Fully clear grid to avoid stale rows/cols
            try:
                self.bit_grid.setRowCount(0)
                self.bit_grid.setColumnCount(0)
            except Exception:
                pass
            return

        # Safely resolve message attributes
        num_bytes = getattr(self.message, 'length', None)
        if num_bytes is None:
            # Fallback to 8 bytes if not provided
            num_bytes = 8
        name = getattr(self.message, 'name', 'Unknown')
        frame_id = getattr(self.message, 'frame_id', None)
        try:
            id_str = f"0x{int(frame_id):X}" if frame_id is not None else "N/A"
        except Exception:
            id_str = "N/A"
        sigs = list(getattr(self.message, 'signals', []) or [])
        self.header_label.setText(f"Message: {name} (ID: {id_str}) - {num_bytes} bytes, {num_bytes * 8} bits, {len(sigs)} signals")

        self.bit_grid.setRowCount(num_bytes)
        self.bit_grid.setColumnCount(8)
        
        self.bit_grid.setHorizontalHeaderLabels([f"Bit {7-i}" for i in range(8)])
        self.bit_grid.setVerticalHeaderLabels([f"{i}" for i in range(num_bytes)])

        for row in range(num_bytes):
            for col in range(8):
                # Calculate the absolute bit position based on grid location
                abs_bit_pos = self._calculate_bit_position(row, col)
                
                item = QTableWidgetItem(str(abs_bit_pos))
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(QFont("Consolas", 8))
                
                # Store the absolute bit position in the item for later styling
                item.setData(Qt.UserRole, abs_bit_pos)
                self.bit_grid.setItem(row, col, item)
        
        self.bit_grid.resizeColumnsToContents()

    def _calculate_bit_position(self, row, col):
        """Calculates the absolute bit position for a cell, always LSB 0."""
        # The visual grid is always MSB-first in the byte (col 0 = bit 7)
        bit_in_byte = 7 - col
        return row * 8 + bit_in_byte

    def _style_grid(self, highlighted_signal=None):
        if not self.message: return

        for row in range(self.bit_grid.rowCount()):
            for col in range(self.bit_grid.columnCount()):
                item = self.bit_grid.item(row, col)
                if not item: continue # Cell might be empty
                
                abs_bit_pos = item.data(Qt.UserRole)
                signal = self.bit_to_signal_map.get(abs_bit_pos)
                
                color = QColor("#3c3c3c") # Default unused color
                if signal:
                    base_color = self.signal_colors.get(signal.name, QColor("#FFFFFF"))
                    
                    if highlighted_signal:
                        if highlighted_signal.name == signal.name:
                            # Make the highlighted signal's bits brighter
                            color = base_color.lighter(150)
                        else:
                            # Make other signals' bits dimmer
                            color = base_color.darker(150)
                    else:
                        # No specific signal is highlighted, use the base color
                        color = base_color
                
                item.setBackground(color)

    def _on_signal_selected(self, current, previous):
        if current:
            signal = current.data(Qt.UserRole)
            self._style_grid(highlighted_signal=signal)
        else:
            self._style_grid(highlighted_signal=None)

# --- Signal List Item Widget ---
class SignalListItemWidget(QWidget):
    def __init__(self, color, signal_name, details):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.color_swatch = QFrame()
        self.color_swatch.setFixedSize(15, 15)
        self.color_swatch.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #555;")

        self.name_label = QLabel(f"<b>{signal_name}</b> ({details})")
        self.name_label.setFont(QFont("Consolas", 9))

        layout.addWidget(self.color_swatch)
        layout.addWidget(self.name_label)

# --- C Code Generation Logic ---
def _validate_signal_attributes(signal):
    """Validate and debug signal attributes."""
    attrs = {}
    for attr in ['name', 'start', 'length', 'scale', 'offset', 'is_signed', 'byte_order']:
        try:
            attrs[attr] = getattr(signal, attr, None)
        except Exception as e:
            attrs[attr] = f"Error: {e}"
    return attrs

def _get_c_type(signal):
    # Get signal attributes safely
    sig_scale = getattr(signal, 'scale', 1.0)
    sig_offset = getattr(signal, 'offset', 0.0)
    sig_is_signed = getattr(signal, 'is_signed', False)
    sig_length = getattr(signal, 'length', 8)
    
    if sig_scale != 1 or sig_offset != 0: 
        return "float"
    if sig_is_signed:
        if sig_length <= 8: 
            return "int8_t"
        if sig_length <= 16: 
            return "int16_t"
        if sig_length <= 32: 
            return "int32_t"
        return "int64_t"
    else:
        if sig_length <= 8: 
            return "uint8_t"
        if sig_length <= 16: 
            return "uint16_t"
        if sig_length <= 32: 
            return "uint32_t"
        return "uint64_t"

def generate_header_code(messages, filename="can_messages.h"):
    """Generate header code for selected messages."""
    if not messages:
        return "// No messages selected"
    
    # Extract base name from filename for include guard
    base_name = filename.replace('.h', '').upper().replace('-', '_').replace('.', '_')
    
    code = [
        f"// Auto-generated by ART_DBC-Code-Generator\n",
        f"#ifndef {base_name}_H",
        f"#define {base_name}_H\n",
        "#include <stdint.h>\n"
    ]
    
    for msg in messages:
        # Get message attributes safely
        msg_name = getattr(msg, 'name', 'Unknown')
        msg_frame_id = getattr(msg, 'frame_id', 0)
        
        code.append(f"// Message: {msg_name} (ID: 0x{msg_frame_id:X})")
        code.append(f"typedef struct {{")
        for sig in msg.signals: 
            # Get signal attributes safely
            sig_scale = getattr(sig, 'scale', 1.0)
            sig_offset = getattr(sig, 'offset', 0.0)
            
            # Add scaling information in comments
            scale_info = ""
            if sig_scale != 1 or sig_offset != 0:
                scale_info = f" // scale={sig_scale}, offset={sig_offset}"
            code.append(f"    {_get_c_type(sig)} {sig.name};{scale_info}")
        code.append(f"}} {msg_name}_t;\n")
        code.append(f"void unpack_{msg_name}(const uint8_t* data, {msg_name}_t* msg);")
        code.append(f"void pack_{msg_name}(const {msg_name}_t* msg, uint8_t* data);\n")
    
    code.append(f"#endif // {base_name}_H")
    return "\n".join(code)

def generate_source_code(messages, filename="can_messages.c"):
    """Generate source code for selected messages."""
    if not messages:
        return "// No messages selected"
    
    # Extract header filename from source filename
    header_filename = filename.replace('.c', '.h')
    
    code = [
        f'// Auto-generated by ART_DBC-Code-Generator\n',
        f'#include "{header_filename}"',
        '#include <string.h> // For memcpy\n'
    ]
    
    for msg in messages:
        # Get message length safely
        msg_length = getattr(msg, 'length', 8)  # Default to 8 bytes if not specified
        
        code.append(f"void unpack_{msg.name}(const uint8_t* data, {msg.name}_t* msg) {{")
        code.append(f"    uint64_t raw_data = 0; memcpy(&raw_data, data, {msg_length});\n")
        
        for sig in msg.signals:
            # Get signal attributes safely
            sig_length = getattr(sig, 'length', 1)
            sig_start = getattr(sig, 'start', 0)
            sig_scale = getattr(sig, 'scale', 1.0)
            sig_offset = getattr(sig, 'offset', 0.0)
            sig_is_signed = getattr(sig, 'is_signed', False)
            
            # Add debug comment for signal attributes
            code.append(f"    // Signal: {sig.name} - start:{sig_start}, length:{sig_length}, scale:{sig_scale}, offset:{sig_offset}, signed:{sig_is_signed}")
            
            # Calculate mask and start bit
            mask = (1 << sig_length) - 1
            start_bit = sig_start
            
            code.append(f"    uint64_t raw_{sig.name} = (raw_data >> {start_bit}) & 0x{mask:X}ULL;")
            
            if sig_is_signed and sig_length < 64:
                sign_bit_mask = 1 << (sig_length - 1)
                # Generate the extension mask as a proper C bit mask
                # This creates a mask like 0xFFFFFF00 for an 8-bit signal
                extension_mask = ((1 << 64) - 1) & ~((1 << sig_length) - 1)
                code.append(f"    if (raw_{sig.name} & 0x{sign_bit_mask:X}ULL) {{ raw_{sig.name} |= 0x{extension_mask:X}ULL; }}")
            
            c_type = _get_c_type(sig)
            if c_type == "float": 
                code.append(f"    // Apply scaling: raw_value * {sig_scale} + {sig_offset}")
                code.append(f"    msg->{sig.name} = (float)raw_{sig.name} * {sig_scale} + {sig_offset};")
            else: 
                code.append(f"    // No scaling applied (raw value)")
                code.append(f"    msg->{sig.name} = ({c_type})raw_{sig.name};")
        
        code.append("}\n")
        
        code.append(f"void pack_{msg.name}(const {msg.name}_t* msg, uint8_t* data) {{")
        code.append("    uint64_t raw_data = 0;\n")
        
        for sig in msg.signals:
            # Get signal attributes safely
            sig_length = getattr(sig, 'length', 1)
            sig_start = getattr(sig, 'start', 0)
            sig_scale = getattr(sig, 'scale', 1.0)
            sig_offset = getattr(sig, 'offset', 0.0)
            
            c_type = _get_c_type(sig)
            if c_type == "float": 
                code.append(f"    uint64_t raw_{sig.name} = (uint64_t)((msg->{sig.name} - ({sig_offset})) / {sig_scale});")
            else: 
                code.append(f"    uint64_t raw_{sig.name} = (uint64_t)msg->{sig.name};")
            
            # Calculate mask and start bit
            mask = (1 << sig_length) - 1
            start_bit = sig_start
            code.append(f"    raw_data |= (raw_{sig.name} & 0x{mask:X}ULL) << {start_bit};")
        
        code.append(f"\n    memcpy(data, &raw_data, {msg_length});")
        code.append("}\n")
    
    return "\n".join(code)

# --- Main Application UI ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DBC to C Code Generator")
        self.setGeometry(100, 100, 900, 700)
        self.db = None
        
        # Set the application icon
        icon_path = self._get_resource_path("apex_orange_ONLY LOGO.png")
        if os.path.exists(icon_path):
            try:
                # Create properly sized icon to prevent stretching
                icon_pixmap = QPixmap(icon_path)
                if not icon_pixmap.isNull():
                    # Create a 32x32 canvas with transparent background
                    canvas = QPixmap(32, 32)
                    canvas.fill(Qt.transparent)
                    
                    # Scale the logo maintaining aspect ratio
                    scaled_logo = icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    # Calculate center position
                    x = (32 - scaled_logo.width()) // 2
                    y = (32 - scaled_logo.height()) // 2
                    
                    # Paint the scaled logo onto the canvas
                    painter = QPainter(canvas)
                    painter.drawPixmap(x, y, scaled_logo)
                    painter.end()
                    
                    self.setWindowIcon(QIcon(canvas))
                else:
                    print("Warning: Could not load icon pixmap")
            except Exception as e:
                print(f"Warning: Could not load icon: {e}")
        else:
            print(f"Warning: Icon file not found: {icon_path}")
        
        # --- Main Layout ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # --- Top Controls ---
        controls_layout = QHBoxLayout()
        self.btn_select = QPushButton("1. Select DBC File")
        self.btn_generate = QPushButton("2. Generate Code")
        self.btn_generate.setEnabled(False)
        self.btn_save = QPushButton("3. Save Files...")
        self.btn_save.setEnabled(False)
        
        controls_layout.addWidget(self.btn_select)
        controls_layout.addWidget(self.btn_generate)
        controls_layout.addWidget(self.btn_save)
        self.layout.addLayout(controls_layout)
        
        # --- Tabbed Interface ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #444; border-radius: 8px; }
            QTabBar::tab { background-color: #4a4a4a; padding: 8px 16px; margin-right: 2px; border-radius: 4px; }
            QTabBar::tab:selected { background-color: #5a5a5a; }
            QTabBar::tab:hover { background-color: #6a6a6a; }
        """)
        
        # --- Tab 1: Bit Layout Viewer ---
        self.bit_viewer = BitLayoutViewer()
        self.tab_widget.addTab(self.bit_viewer, "Bit Layout")
        
        # --- Tab 2: Code Generation ---
        code_widget = QWidget()
        code_layout = QVBoxLayout(code_widget)
        code_layout.setContentsMargins(0, 0, 0, 0)
        
        # Code Display using a Splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Header file display
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add spacing above the header label
        header_layout.addSpacing(10)
        header_label = QLabel("can_messages.h")
        header_label.setObjectName("header_label")
        header_layout.addWidget(header_label)
        
        self.txt_header = QTextEdit()
        self.txt_header.setFont(QFont("Consolas", 10))
        self.highlighter_h = CppHighlighter(self.txt_header.document())
        header_layout.addWidget(self.txt_header)
        splitter.addWidget(header_widget)
        
        # Source file display
        source_widget = QWidget()
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_label = QLabel("can_messages.c")
        source_label.setObjectName("source_label")
        source_layout.addWidget(source_label)
        self.txt_source = QTextEdit()
        self.txt_source.setFont(QFont("Consolas", 10))
        self.highlighter_c = CppHighlighter(self.txt_source.document())
        source_layout.addWidget(self.txt_source)
        splitter.addWidget(source_widget)
        
        splitter.setSizes([300, 400])  # Set initial size ratio
        code_layout.addWidget(splitter)
        
        self.tab_widget.addTab(code_widget, "Generate Code")
        
        self.layout.addWidget(self.tab_widget)
        
        # --- Bottom Logo Section ---
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 2, 8, 2)  # Left, Top, Right, Bottom margins - reduced
        logo_layout.addStretch()  # Left spacing - pushes logo to right
        
        # Create clickable logo label
        self.logo_label = QLabel()
        logo_pixmap = QPixmap(self._get_resource_path("apex_orange_ONLY LOGO.png"))
        if not logo_pixmap.isNull():
            # Scale logo to larger size (max 45px height)
            scaled_pixmap = logo_pixmap.scaled(45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
            self.logo_label.setCursor(QCursor(Qt.PointingHandCursor))
            self.logo_label.setToolTip("Click to visit Apex Race Tech")
            self.logo_label.mousePressEvent = self.open_website
        else:
            self.logo_label.setText("ART")
            self.logo_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF6600;")
        
        logo_layout.addWidget(self.logo_label)
        self.layout.addLayout(logo_layout)
        
        # --- Status Bar ---
        self.setStatusBar(QStatusBar())
        
        # --- Connect Signals ---
        self.btn_select.clicked.connect(self.select_dbc_file)
        self.btn_generate.clicked.connect(self.generate_code)
        self.btn_save.clicked.connect(self.save_files)
        
        self.apply_stylesheet()

    def _get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        
        return os.path.join(base_path, relative_path)

    def open_website(self, event):
        """Open Apex Race Tech website when logo is clicked."""
        try:
            from PyQt5.QtCore import QUrl
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl("https://apexracetech.in/"))
        except ImportError:
            import webbrowser
            webbrowser.open("https://apexracetech.in/")

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { 
                background-color: #2b2b2b; 
                border-radius: 12px;
            }
            QWidget { 
                background-color: #2b2b2b; 
                color: #f0f0f0; 
                font-size: 10pt; 
            }
            QLabel { 
                font-weight: bold; 
                border-radius: 8px;
            }
            QPushButton { 
                background-color: #4a4a4a; 
                padding: 8px; 
                border-radius: 8px; 
                border: none;
            }
            QPushButton:hover { 
                background-color: #5a5a5a; 
                border-radius: 8px;
            }
            QPushButton:disabled { 
                background-color: #333; 
                color: #777; 
                border-radius: 8px;
            }
            QTextEdit { 
                background-color: #1e1e1e; 
                border: 1px solid #444; 
                border-radius: 8px;
                padding: 8px;
            }
            QStatusBar { 
                color: #bbbbbb; 
                border-radius: 8px;
            }
            QSplitter::handle {
                background-color: #444;
                border-radius: 4px;
            }
            QSplitter::handle:hover {
                background-color: #555;
            }
        """)

    def select_dbc_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select DBC File", "", "DBC Files (*.dbc);;All Files (*)")
        if not path: 
            return
        
        try:
            self.db = cantools.database.load_file(path)
            self.statusBar().showMessage(f"Loaded '{os.path.basename(path)}'", 5000)
            self.btn_generate.setEnabled(True)
            self.txt_header.clear()
            self.txt_source.clear()
            self.btn_save.setEnabled(False)
            
            # Load all messages into the bit viewer
            if self.db.messages:
                self.bit_viewer.load_database(self.db)
                self.statusBar().showMessage(f"Loaded '{os.path.basename(path)}' with {len(self.db.messages)} messages - Use Bit Layout tab to view individual messages", 5000)
            
            QMessageBox.information(
                self, "Success", 
                f"Successfully loaded and parsed '{os.path.basename(path)}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to parse DBC file:\n{e}")
            self.db = None
            self.btn_generate.setEnabled(False)
            # Clear the bit viewer
            self.bit_viewer.load_database(None)
            
    def generate_code(self):
        if not self.db: 
            return
        
        # Get selected messages from the bit viewer
        selected_messages = self.bit_viewer.get_selected_messages()
        
        if not selected_messages:
            QMessageBox.warning(self, "No Messages Selected", 
                              "Please select at least one message in the Bit Layout tab before generating code.")
            return
        
        # Generate filenames based on selected messages
        if len(selected_messages) == 1:
            # Single message - use message name
            message_name = selected_messages[0].name
            # Clean the message name for filename (remove special characters, spaces)
            clean_name = "".join(c for c in message_name if c.isalnum() or c in ('_', '-')).lower()
            header_filename = f"{clean_name}.h"
            source_filename = f"{clean_name}.c"
        else:
            # Multiple messages - create descriptive name from selected messages
            message_names = [msg.name for msg in selected_messages]
            # Create a base name from the first few message names
            if len(message_names) <= 3:
                base_name = "_".join([name.lower() for name in message_names])
            else:
                base_name = f"{message_names[0].lower()}_and_{len(message_names)-1}_more"
            
            # Clean the base name for filename
            clean_base_name = "".join(c for c in base_name if c.isalnum() or c in ('_', '-'))
            header_filename = f"{clean_base_name}.h"
            source_filename = f"{clean_base_name}.c"
        
        # Update the labels in the code generation tab
        self.tab_widget.widget(1).findChild(QLabel, "header_label").setText(header_filename)
        self.tab_widget.widget(1).findChild(QLabel, "source_label").setText(source_filename)
        
        self.txt_header.setPlainText(generate_header_code(selected_messages, header_filename))
        self.txt_source.setPlainText(generate_source_code(selected_messages, source_filename))
        self.btn_save.setEnabled(True)
        self.statusBar().showMessage(f"C code generated for {len(selected_messages)} message(s).", 3000)
        
        # Automatically switch to the Generate Code tab
        self.tab_widget.setCurrentIndex(1)
        
    def save_files(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Save C Files")
        if not dir_path: 
            return
        
        try:
            # Get the current filenames from the labels
            header_filename = self.tab_widget.widget(1).findChild(QLabel, "header_label").text()
            source_filename = self.tab_widget.widget(1).findChild(QLabel, "source_label").text()
            
            with open(os.path.join(dir_path, header_filename), "w", encoding='utf-8') as f:
                f.write(self.txt_header.toPlainText())
            with open(os.path.join(dir_path, source_filename), "w", encoding='utf-8') as f:
                f.write(self.txt_source.toPlainText())
            QMessageBox.information(
                self, "Success", 
                f"Files saved successfully in:\n{dir_path}\n\nHeader: {header_filename}\nSource: {source_filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save files:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())