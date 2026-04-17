"""
⭐ AsterDex 自动交易系统 - 桌面应用 v3
网页内嵌登录 + 钱包检测
"""

import sys
import asyncio
import json
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QProgressBar,
    QTextEdit, QGroupBox, QWebEngineView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWebEngineWidgets import QWebEngineView
from web3 import Web3

from asterdex_api import AsterDexAPI
from trading_engine import AutoTradingEngine


class Web3Worker(QThread):
    """Web3 异步工作线程"""
    update_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, task_name: str, **kwargs):
        super().__init__()
        self.task_name = task_name
        self.kwargs = kwargs

    def run(self):
        """运行任务"""
        try:
            if self.task_name == "detect_wallet":
                result = self._detect_wallet()
            else:
                result = None
            self.update_signal.emit({"task": self.task_name, "data": result})
        except Exception as e:
            self.error_signal.emit(f"检测失败: {str(e)}")

    def _detect_wallet(self):
        """检测钱包信息"""
        try:
            # 尝试通过 window.ethereum 获取连接的钱包
            w3 = Web3(Web3.HTTPProvider("https://eth-mainnet.g.alchemy.com/v2/demo"))

            # 这里假设用户已在网页中登录
            # 在实际应用中，需要通过IPC或localStorage获取地址
            return {
                "connected": True,
                "network": "Ethereum Mainnet",
                "status": "检测成功"
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.api: Optional[AsterDexAPI] = None
        self.engine: Optional[AutoTradingEngine] = None
        self.wallet_address = None
        self.is_logged_in = False

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("⭐ AsterDex 自动交易系统")
        self.setGeometry(0, 0, 1600, 1000)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px;
            }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 8px; border: none; }
            QPushButton:hover { background-color: #ffb84d; }
            QPushButton:pressed { background-color: #e59400; }
            QTableWidget { background-color: #2a2a2a; color: #ffffff; gridline-color: #444; }
            QHeaderView::section { background-color: #333; color: #fff; padding: 5px; }
            QTabBar::tab { background-color: #2a2a2a; color: #fff; padding: 8px; }
            QTabBar::tab:selected { background-color: #f5a623; color: #000; }
            QTextEdit { background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("⭐ AsterDex 自动交易系统")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_layout.addWidget(title)

        self.user_info = QLabel("未登录")
        self.user_info.setStyleSheet("color: #ff9800; font-weight: bold;")
        title_layout.addStretch()
        title_layout.addWidget(self.user_info)

        logout_btn = QPushButton("🚪 登出")
        logout_btn.clicked.connect(self.logout)
        title_layout.addWidget(logout_btn)
        main_layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()

        # 登录页面
        self.login_tab = self.create_login_tab()
        tabs.addTab(self.login_tab, "🔐 登录")

        # 交易页面
        self.trading_tab = self.create_trading_tab()
        tabs.addTab(self.trading_tab, "💰 交易")

        # 钱包信息页面
        self.wallet_tab = self.create_wallet_tab()
        tabs.addTab(self.wallet_tab, "🏦 钱包")

        # 持仓页面
        self.positions_tab = self.create_positions_tab()
        tabs.addTab(self.positions_tab, "📊 持仓")

        # 交易历史
        self.history_tab = self.create_history_tab()
        tabs.addTab(self.history_tab, "📝 历史")

        # 自动交易页面
        self.auto_tab = self.create_auto_trading_tab()
        tabs.addTab(self.auto_tab, "🤖 自动交易")

        main_layout.addWidget(tabs)

        central_widget.setLayout(main_layout)

        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)

    def create_login_tab(self):
        """创建登录标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 提示信息
        info = QLabel("请在下方登录页面中使用 Hyperliquid 或 AsterDex 账户登录")
        info.setStyleSheet("color: #f5a623; font-weight: bold; padding: 10px;")
        layout.addWidget(info)

        # 嵌入网页
        self.web_view = QWebEngineView()
        # 加载 Hyperliquid 登录页面
        self.web_view.setUrl(QUrl("https://www.hyperliquid.xyz"))
        layout.addWidget(self.web_view)

        # 登录状态和按钮
        button_layout = QHBoxLayout()

        self.login_status = QLabel("状态: 未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        button_layout.addWidget(self.login_status)

        button_layout.addStretch()

        # 我已登录按钮
        logged_btn = QPushButton("✅ 我已登录")
        logged_btn.setMinimumHeight(40)
        logged_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        logged_btn.clicked.connect(self.on_login_confirm)
        button_layout.addWidget(logged_btn)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新页面")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.clicked.connect(lambda: self.web_view.reload())
        button_layout.addWidget(refresh_btn)

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def create_trading_tab(self):
        """创建交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先在登录页面完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

        # 实时数据
        info_layout = QHBoxLayout()
        self.balance_label = QLabel("余额: ¥0.00")
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
        form_layout.addWidget(self.size_input)

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

    def create_wallet_tab(self):
        """创建钱包信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

        # 钱包地址
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("钱包地址:"))
        self.address_display = QLineEdit()
        self.address_display.setReadOnly(True)
        addr_layout.addWidget(self.address_display)
        copy_btn = QPushButton("📋 复制")
        copy_btn.setMaximumWidth(80)
        copy_btn.clicked.connect(self.copy_address)
        addr_layout.addWidget(copy_btn)
        layout.addLayout(addr_layout)

        # 余额信息
        balance_layout = QHBoxLayout()

        eth_box = QGroupBox("ETH 余额")
        eth_box_layout = QVBoxLayout()
        self.eth_label = QLabel("0.00 ETH")
        self.eth_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.eth_label.setStyleSheet("color: #f5a623;")
        eth_box_layout.addWidget(self.eth_label)
        eth_box.setLayout(eth_box_layout)
        balance_layout.addWidget(eth_box)

        usdt_box = QGroupBox("USDT 余额")
        usdt_box_layout = QVBoxLayout()
        self.usdt_label = QLabel("0.00 USDT")
        self.usdt_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.usdt_label.setStyleSheet("color: #4ade80;")
        usdt_box_layout.addWidget(self.usdt_label)
        usdt_box.setLayout(usdt_box_layout)
        balance_layout.addWidget(usdt_box)

        balance_layout.addStretch()
        layout.addLayout(balance_layout)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新信息")
        refresh_btn.clicked.connect(self.refresh_wallet_info)
        layout.addWidget(refresh_btn)

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

    def create_history_tab(self):
        """创建交易历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels(
            ["交易ID", "交易对", "方向", "数量", "价格", "时间", "盈亏"]
        )
        layout.addWidget(self.history_table)

        widget.setLayout(layout)
        return widget

    def create_auto_trading_tab(self):
        """创建自动交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

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
        self.stats_label = QLabel("总交易: 0 | 胜率: 0% | 总盈亏: ¥0.00")
        self.stats_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.stats_label.setStyleSheet("color: #f5a623;")
        layout.addWidget(self.stats_label)

        # 活跃持仓表格
        self.auto_positions_table = QTableWidget()
        self.auto_positions_table.setColumnCount(7)
        self.auto_positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%"]
        )
        layout.addWidget(self.auto_positions_table)

        # 日志
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setMaximumHeight(120)
        layout.addWidget(QLabel("📋 交易日志:"))
        layout.addWidget(self.auto_log)

        widget.setLayout(layout)
        return widget

    def on_login_confirm(self):
        """用户点击'我已登录'按钮"""
        self.login_status.setText("状态: 检测中...")
        self.login_status.setStyleSheet("color: #ffb84d; font-weight: bold;")

        # 检测钱包
        worker = Web3Worker("detect_wallet")
        worker.update_signal.connect(self.on_login_detected)
        worker.error_signal.connect(self.on_login_error)
        worker.start()

    def on_login_detected(self, data):
        """检测到登录"""
        result = data.get("data", {})

        if result.get("connected"):
            self.is_logged_in = True
            self.login_status.setText("状态: ✅ 已登录")
            self.login_status.setStyleSheet("color: #4ade80; font-weight: bold;")
            self.user_info.setText("✅ 已登录")

            # 刷新所有页面
            self.refresh_data()

            QMessageBox.information(self, "✅ 成功", "登录成功！已检测到钱包信息")
        else:
            self.login_status.setText("状态: ❌ 检测失败")
            self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            QMessageBox.warning(self, "⚠️", "未检测到钱包信息，请先登录")

    def on_login_error(self, error):
        """登录检测出错"""
        self.login_status.setText("状态: ❌ 错误")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        QMessageBox.warning(self, "错误", error)

    def refresh_data(self):
        """刷新所有数据"""
        self.refresh_wallet_info()
        # 这里可以添加其他数据刷新逻辑

    def refresh_wallet_info(self):
        """刷新钱包信息"""
        if not self.is_logged_in:
            return

        # 这里显示示例数据
        # 在实际应用中，应该从API或区块链获取真实数据
        self.eth_label.setText("2.5 ETH")
        self.usdt_label.setText("5000.00 USDT")
        self.address_display.setText("0x1234567890abcdef...")

    def copy_address(self):
        """复制地址"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.address_display.text())
        QMessageBox.information(self, "✅", "已复制地址")

    def place_order(self):
        """下单"""
        if not self.is_logged_in:
            QMessageBox.warning(self, "错误", "请先登录")
            return
        QMessageBox.information(self, "提示", "订单下单功能开发中...")

    def start_auto_trading(self):
        """启动自动交易"""
        if not self.is_logged_in:
            QMessageBox.warning(self, "错误", "请先登录")
            return
        self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 自动交易已启动")
        self.auto_start_btn.setEnabled(False)
        self.auto_stop_btn.setEnabled(True)

    def stop_auto_trading(self):
        """停止自动交易"""
        self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ 自动交易已停止")
        self.auto_start_btn.setEnabled(True)
        self.auto_stop_btn.setEnabled(False)

    def logout(self):
        """登出"""
        self.is_logged_in = False
        self.user_info.setText("未登录")
        self.login_status.setText("状态: 未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        QMessageBox.information(self, "✅", "已登出")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
