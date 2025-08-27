import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QFrame, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QPushButton, QSizePolicy
)
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QSize

# --- MOCK OBJECTS FOR STANDALONE TESTING ---
class MockSignal:
    def __init__(self, name, start, length, byte_order):
        self.name = name
        self.start = start
        self.length = length
        self.byte_order = byte_order

class MockMessage:
    def __init__(self, name, frame_id, length, signals):
        self.name = name
        self.frame_id = frame_id
        self.length = length
        self.signals = signals

# --- CUSTOM WIDGET FOR THE RICH SIGNAL LIST ---
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

# --- THE MAIN EMBEDDABLE WIDGET ---
class BitLayoutViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.message = None
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

# --- STANDALONE EXAMPLE USAGE ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Create mock messages with BE and LE signals
    mock_signals_fd = [
        MockSignal("New_Signal_1", 0, 8, 'big_endian'),
        MockSignal("New_Signal_2", 8, 8, 'big_endian'),
        MockSignal("New_Signal_3", 16, 8, 'big_endian'),
        MockSignal("New_Signal_4", 24, 8, 'big_endian'),
        MockSignal("New_Signal_5", 32, 8, 'big_endian'),
        MockSignal("New_Signal_6", 40, 8, 'big_endian'),
        MockSignal("New_Signal_7", 504, 8, 'big_endian'), # Example of a signal much further down
    ]
    mock_message_fd = MockMessage("New_Message_1", 0x0, 64, mock_signals_fd)

    main_window = QMainWindow()
    main_window.setWindowTitle("Bit Layout Viewer - Final Design")
    main_window.setGeometry(100, 100, 900, 600)
    
    # --- How to embed the viewer ---
    bit_viewer = BitLayoutViewer()
    main_window.setCentralWidget(bit_viewer)
    
    # Load the message
    bit_viewer.display_message(mock_message_fd)
    
    main_window.show()
    sys.exit(app.exec_())