"""
⭐ AsterDex 自动交易系统 - 桌面应用 v2
支持 WalletConnect 钱包扫码登录
"""

import sys
import asyncio
import qrcode
from io import BytesIO
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QDialog, QProgressBar,
    QStatusBar, QTextEdit, QFormLayout, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap, QImage
from PyQt6.QtWidgets import QScrollArea
from web3 import Web3
from eth_account.messages import encode_defunct
import json
import time

from asterdex_api import AsterDexAPI
from trading_engine import (
    AutoTradingEngine, MomentumStrategy, MeanReversionStrategy,
    TrendFollowingStrategy, OrderSide, PositionSide
)


class WalletConnectDialog(QDialog):
    """WalletConnect 登录对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wallet_address = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🔐 WalletConnect 登录")
        self.setGeometry(100, 100, 600, 700)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLineEdit { background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px; }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 10px; border: none; }
            QPushButton:hover { background-color: #ffb84d; }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # 标题
        title = QLabel("🔐 WalletConnect 扫码登录")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # 二维码
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.qr_label)

        # 连接码
        self.uri_text = QTextEdit()
        self.uri_text.setReadOnly(True)
        self.uri_text.setMaximumHeight(60)
        layout.addWidget(QLabel("连接URI（复制到手机钱包）:"))
        layout.addWidget(self.uri_text)

        # 或手动输入地址
        layout.addWidget(QLabel("或者直接输入钱包地址:"))
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("0x...")
        layout.addWidget(self.address_input)

        # 按钮
        button_layout = QHBoxLayout()

        generate_btn = QPushButton("🔄 生成二维码")
        generate_btn.clicked.connect(self.generate_qr)
        button_layout.addWidget(generate_btn)

        connect_btn = QPushButton("✅ 连接钱包")
        connect_btn.clicked.connect(self.accept)
        button_layout.addWidget(connect_btn)

        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def generate_qr(self):
        """生成WalletConnect二维码"""
        # 生成示例URI
        uri = "wc:9b9b9b9b-9b9b-9b9b-9b9b-9b9b9b9b9b9b@1?relay-protocol=irn&symKey=abcd1234"

        self.uri_text.setText(uri)

        # 生成二维码
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # 转换为PyQt6格式
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        qimage = QImage()
        qimage.loadFromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimage)
        self.qr_label.setPixmap(pixmap.scaledToWidth(300))

    def get_wallet(self):
        """获取钱包地址"""
        if self.exec() == QDialog.DialogCode.Accepted:
            address = self.address_input.text().strip()
            if address.startswith("0x") and len(address) == 42:
                return address
            else:
                QMessageBox.warning(self, "错误", "请输入有效的钱包地址 (0x...)")
                return None
        return None


class Web3Worker(QThread):
    """Web3 异步工作线程"""
    update_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, task_name: str, **kwargs):
        super().__init__()
        self.task_name = task_name
        self.kwargs = kwargs
        self.running = True

    def run(self):
        """运行任务"""
        try:
            if self.task_name == "get_balance":
                result = self._get_balance()
            elif self.task_name == "get_token_balance":
                result = self._get_token_balance()
            else:
                result = None

            self.update_signal.emit({"task": self.task_name, "data": result})
        except Exception as e:
            self.error_signal.emit(f"{self.task_name} 失败: {str(e)}")

    def _get_balance(self):
        """获取ETH余额"""
        try:
            w3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/demo"))
            address = self.kwargs.get("address")
            balance_wei = w3.eth.get_balance(address)
            balance_eth = Web3.from_wei(balance_wei, 'ether')
            return {"balance": float(balance_eth), "address": address}
        except:
            return {"balance": 0, "address": self.kwargs.get("address")}

    def _get_token_balance(self):
        """获取代币余额（USDT等）"""
        try:
            w3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/demo"))

            # USDT ABI (简化版)
            usdt_abi = '[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]'

            # USDT 合约地址
            usdt_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"

            contract = w3.eth.contract(address=usdt_address, abi=json.loads(usdt_abi))
            address = self.kwargs.get("address")
            balance = contract.functions.balanceOf(address).call()
            balance_usdt = balance / 1e6

            return {"balance": float(balance_usdt), "address": address}
        except:
            return {"balance": 0, "address": self.kwargs.get("address")}


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.api: AsterDexAPI = None
        self.engine: AutoTradingEngine = None
        self.wallet_address = None
        self.eth_balance = 0
        self.usdt_balance = 0

        self.init_ui()
        self.show_wallet_login()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("⭐ AsterDex 自动交易系统 - WalletConnect")
        self.setGeometry(0, 0, 1400, 900)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px;
            }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 8px; border: none; }
            QPushButton:hover { background-color: #ffb84d; }
            QTableWidget { background-color: #2a2a2a; color: #ffffff; gridline-color: #444; }
            QHeaderView::section { background-color: #333; color: #fff; padding: 5px; }
            QTabBar::tab { background-color: #2a2a2a; color: #fff; padding: 8px; }
            QTabBar::tab:selected { background-color: #f5a623; color: #000; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("⭐ AsterDex 自动交易系统")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_layout.addWidget(title)

        self.user_info = QLabel("未连接钱包")
        self.user_info.setStyleSheet("color: #f5a623; font-weight: bold;")
        title_layout.addStretch()
        title_layout.addWidget(self.user_info)

        logout_btn = QPushButton("🚪 断开钱包")
        logout_btn.clicked.connect(self.disconnect_wallet)
        title_layout.addWidget(logout_btn)
        main_layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()

        # 交易页面
        self.trading_tab = self.create_trading_tab()
        tabs.addTab(self.trading_tab, "💰 交易")

        # 钱包信息页面
        self.wallet_tab = self.create_wallet_tab()
        tabs.addTab(self.wallet_tab, "🏦 钱包")

        # 持仓页面
        self.positions_tab = self.create_positions_tab()
        tabs.addTab(self.positions_tab, "📊 持仓")

        # 自动交易页面
        self.auto_tab = self.create_auto_trading_tab()
        tabs.addTab(self.auto_tab, "🤖 自动交易")

        main_layout.addWidget(tabs)

        central_widget.setLayout(main_layout)

        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_wallet_data)
        self.refresh_timer.start(10000)

    def create_wallet_tab(self):
        """创建钱包信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 钱包地址
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("钱包地址:"))
        self.address_display = QLineEdit()
        self.address_display.setReadOnly(True)
        addr_layout.addWidget(self.address_display)
        copy_btn = QPushButton("📋 复制")
        copy_btn.clicked.connect(self.copy_address)
        copy_btn.setMaximumWidth(80)
        addr_layout.addWidget(copy_btn)
        layout.addLayout(addr_layout)

        # 余额信息
        balance_layout = QHBoxLayout()

        eth_box = QGroupBox("ETH 余额")
        eth_layout = QVBoxLayout()
        self.eth_label = QLabel("0.00 ETH")
        self.eth_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.eth_label.setStyleSheet("color: #f5a623;")
        eth_layout.addWidget(self.eth_label)
        eth_box.setLayout(eth_layout)
        balance_layout.addWidget(eth_box)

        usdt_box = QGroupBox("USDT 余额")
        usdt_layout = QVBoxLayout()
        self.usdt_label = QLabel("0.00 USDT")
        self.usdt_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.usdt_label.setStyleSheet("color: #4ade80;")
        usdt_layout.addWidget(self.usdt_label)
        usdt_box.setLayout(usdt_layout)
        balance_layout.addWidget(usdt_box)

        balance_layout.addStretch()
        layout.addLayout(balance_layout)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新余额")
        refresh_btn.clicked.connect(self.refresh_wallet_data)
        layout.addWidget(refresh_btn)

        # 交易记录
        layout.addWidget(QLabel("最近交易:"))
        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(4)
        self.tx_table.setHorizontalHeaderLabels(["时间", "类型", "金额", "状态"])
        layout.addWidget(self.tx_table)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_trading_tab(self):
        """创建交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 实时数据
        info_layout = QHBoxLayout()
        self.balance_label = QLabel("ETH 余额: 0.00")
        self.balance_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.balance_label.setStyleSheet("color: #f5a623;")
        info_layout.addWidget(self.balance_label)

        self.price_label = QLabel("BTCUSDT: ¥0.00")
        self.price_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addWidget(self.price_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 下单表单
        form_layout = QHBoxLayout()

        form_layout.addWidget(QLabel("交易对:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        form_layout.addWidget(self.symbol_combo)

        form_layout.addWidget(QLabel("方向:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["🟢 买入", "🔴 卖出"])
        form_layout.addWidget(self.side_combo)

        form_layout.addWidget(QLabel("数量:"))
        self.size_input = QDoubleSpinBox()
        self.size_input.setValue(1.0)
        self.size_input.setMinimum(0.001)
        form_layout.addWidget(self.size_input)

        form_layout.addWidget(QLabel("价格:"))
        self.price_input = QDoubleSpinBox()
        self.price_input.setValue(0)
        form_layout.addWidget(self.price_input)

        form_layout.addWidget(QLabel("杠杆:"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setValue(1)
        self.leverage_spin.setMaximum(10)
        form_layout.addWidget(self.leverage_spin)

        order_btn = QPushButton("📤 下单")
        order_btn.clicked.connect(self.place_order)
        form_layout.addWidget(order_btn)

        layout.addLayout(form_layout)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_positions_tab(self):
        """创建持仓标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%", "操作"]
        )
        layout.addWidget(self.positions_table)

        widget.setLayout(layout)
        return widget

    def create_auto_trading_tab(self):
        """创建自动交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 策略选择
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("选择策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "📈 Momentum (动量策略)",
            "↔️ Mean Reversion (均值回归)",
            "🔁 Trend Following (趋势跟踪)"
        ])
        strategy_layout.addWidget(self.strategy_combo)

        strategy_layout.addWidget(QLabel("交易对:"))
        self.auto_symbol_combo = QComboBox()
        self.auto_symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        strategy_layout.addWidget(self.auto_symbol_combo)

        self.auto_start_btn = QPushButton("🚀 启动")
        self.auto_start_btn.clicked.connect(self.start_auto_trading)
        strategy_layout.addWidget(self.auto_start_btn)

        self.auto_stop_btn = QPushButton("⏹️ 停止")
        self.auto_stop_btn.clicked.connect(self.stop_auto_trading)
        self.auto_stop_btn.setEnabled(False)
        strategy_layout.addWidget(self.auto_stop_btn)

        layout.addLayout(strategy_layout)

        # 统计信息
        self.stats_label = QLabel("总交易: 0 | 胜率: 0% | 总盈亏: ¥0.00 | 活跃持仓: 0")
        self.stats_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.stats_label.setStyleSheet("color: #f5a623;")
        layout.addWidget(self.stats_label)

        # 活跃持仓
        self.auto_positions_table = QTableWidget()
        self.auto_positions_table.setColumnCount(7)
        self.auto_positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%"]
        )
        layout.addWidget(self.auto_positions_table)

        # 日志
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setMaximumHeight(150)
        layout.addWidget(QLabel("📋 交易日志:"))
        layout.addWidget(self.auto_log)

        widget.setLayout(layout)
        return widget

    def show_wallet_login(self):
        """显示钱包登录对话框"""
        dialog = WalletConnectDialog(self)
        address = dialog.get_wallet()

        if address:
            self.wallet_address = address
            self.address_display.setText(address)
            self.user_info.setText(f"✅ {address[:10]}...{address[-8:]}")

            # 初始化API（使用钱包地址作为用户ID）
            self.api = AsterDexAPI(address, address, testnet=False)
            self.engine = AutoTradingEngine(self.api, address)

            self.refresh_wallet_data()
        else:
            sys.exit()

    def disconnect_wallet(self):
        """断开钱包"""
        self.api = None
        self.engine = None
        self.wallet_address = None
        self.show_wallet_login()

    def refresh_wallet_data(self):
        """刷新钱包数据"""
        if not self.wallet_address:
            return

        # 获取ETH余额
        worker = Web3Worker("get_balance", address=self.wallet_address)
        worker.update_signal.connect(self.on_balance_updated)
        worker.start()

        # 获取USDT余额
        worker = Web3Worker("get_token_balance", address=self.wallet_address)
        worker.update_signal.connect(self.on_token_balance_updated)
        worker.start()

    def on_balance_updated(self, data):
        """余额更新"""
        result = data.get("data", {})
        self.eth_balance = result.get("balance", 0)
        self.eth_label.setText(f"{self.eth_balance:.4f} ETH")
        self.balance_label.setText(f"ETH 余额: {self.eth_balance:.4f}")

    def on_token_balance_updated(self, data):
        """代币余额更新"""
        result = data.get("data", {})
        self.usdt_balance = result.get("balance", 0)
        self.usdt_label.setText(f"{self.usdt_balance:.2f} USDT")

    def copy_address(self):
        """复制地址到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.wallet_address)
        QMessageBox.information(self, "✅", "已复制到剪贴板")

    def place_order(self):
        """下单"""
        if not self.api:
            QMessageBox.warning(self, "错误", "请先连接钱包")
            return
        QMessageBox.information(self, "提示", "订单功能集成中...")

    def start_auto_trading(self):
        """启动自动交易"""
        QMessageBox.information(self, "提示", "自动交易启动中...")

    def stop_auto_trading(self):
        """停止自动交易"""
        QMessageBox.information(self, "提示", "自动交易已停止")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
